"""Routines to train and run a classifier on relevance of geolocations.

The main class MashNet packages routines to preprocess data and train, 
evaluate, and run a model. It requires: 

- a compiled Keras Model instance, e.g. from geoloc_model190701.py
- an optional text vectorizer with encode() method if text is to be parsed
 as part of the model

See GeolocTrainingv1.ipynb for usage.

The class operates on 'locations_data', a list of dicts of the following form:

{'address': 'Southern Cross WA 6426, Australia',
 'boundingbox': [119.287784, -31.2682721, 119.367784, -31.1882721],
 'cluster': ['Kalgoorlie-Boulder',
  'Mt Marion',
  'West Kalgoorlie',
  'Kambalda',
  'WA',
  'Kwinana',
  'Mt Holland',
  'Mt Cattlin',
  'Port Hedland',
  'Wodgina',
  'Southern Cross'],
 'cluster_ratio': 0.7857142857142857,
 'label': 'relevant',
 'lat': -31.2282721,
 'lon': 119.327784,
 'mentions': ['Now there are seven operating mines, with the Mt Holland mine near Southern Cross due to come into production next year.'],
 'osm_url': 'https://www.openstreetmap.org/?mlat=-31.22827&mlon=119.32778#map=17/-31.22827/119.32778',
 'relevance': 0.164267,
 'text': 'Southern Cross'}

The MashNet is tolerant to missing dict keys but requires a 'label' for any
training and validation data samples.

"""
from collections import Counter
import datetime
from inspect import getsourcefile
import os
import sys

from keras.callbacks import ModelCheckpoint, TensorBoard
import numpy as np
import pyproj
import shapely.geometry
from sklearn.externals import joblib
from sklearn.preprocessing import LabelBinarizer

MAX_MENTIONS = 6

class MashNet(object):
    """Class to train and run a classifier on relevance of geolocations.

    External methods:
        predict: Run prediction for a specified output layer.
        predict_relevance: Return the name and probability of the predicted 
            class.
        test: Evaluate the model on a test set of locations data.
        train: Train the estimator. 
        prep_features: Extract quantitative data, vectorized text, and labels.

    Attributes:
        estimator: Keras Model instance
        num_losses: Number of loss functions in the model 
        binarizer: Typically, an instance of LabelBinarizer() to convert
            named labels to one-hots
        vectorizer: Optional text vectorizer with encode() method

    """
    def __init__(self, model, binarizer=None, vectorizer=None):
        self.estimator = model
        self.num_losses = len(model.loss_functions)
        self.binarizer = binarizer if binarizer else LabelBinarizer()
        self.vectorizer = vectorizer

    def predict(self, locations_data, output_name=None):
        """Run prediction for a specified output layer.
        
        Arguments:
            locations_data: List of dicts of locations data.
            output_name: Keras layer name. If None or if name not found, 
                predictions are returned for the last available model metric. 

        Returns: Array.
        """
        if self.num_losses == 1:
            return self._predict_all(locations_data)

        if output_name:
            for n, o in enumerate(self.estimator.output):
                if output_name in o.name:
                    return self._predict_all(locations_data)[n]
        return self._predict_all(locations_data)[-1]          

    def _predict_all(self, locations_data):
        """Run prediction for all model outputs."""
        features, _ = self.prep_features(locations_data)
        probabilities = self.estimator.predict(features)
        return probabilities
    
    def predict_relevance(self, locations_data, output_name=None):
        """Return the name and probability of the predicted class.

        Arguments:
            locations_data: List of dicts of locations data.
            output_name: Keras layer name. If None or if name not found, 
                predictions are returned for the last available model metric. 

        Returns: List of dicts of form {class name: probability}
        """
        probabilities = self.predict(locations_data)
        labelings = []
        for location_probs in probabilities:
            argmax = np.argmax(location_probs)
            labelings.append({
                self.binarizer.classes_[argmax]: location_probs[argmax]})
        return labelings

    def test(self, test_set):
        """Evaluate the model on a test set of locations data."""
        metrics = self.estimator.metrics_names
        test_x, test_y = self.prep_features(test_set, with_labels=True)
        evals = self.estimator.evaluate(
            test_x, [test_y for _ in range(self.num_losses)])
        return {m:e for m,e in zip(metrics, evals)}
        
    def train(self, train_set, val_set, metric_name=None, batch_size=10,
              epochs=500):
        """Train the estimator.  

        Arguments: 
            train_set: List of location data dicts, each including a 'label'
            val_set: List of location data dicts, each including a 'label'
            metric_name: Name of model metric for validation. If None or 
                name is not found, the last available metric is applied.
            batch_size
            epochs

        Returns: None
        """
        checkpt_dir = os.path.join(
            os.path.dirname(os.path.abspath(getsourcefile(lambda:0))),
            'training{}'.format(datetime.datetime.now().isoformat()))
        if not os.path.exists(checkpt_dir):
            os.mkdir(checkpt_dir)
        log_dir = checkpt_dir + '_logs'

        if metric_name and metric_name in self.estimator.metrics_names:
            val_acc = 'val_' + metric_name
        else:
            val_acc = 'val_' + self.estimator.metrics_names[-1]
        model_checkpoint = ModelCheckpoint(
            os.path.join(checkpt_dir, 'ChkPtEp{epoch:02d}.hdf5'),
            monitor=val_acc, verbose=1, save_best_only=True)
        
        train_x, train_y = self.prep_features(
            train_set, with_labels=True, fit_binarizer=True)
        val_x, val_y = self.prep_features(val_set, with_labels=True)

        self.estimator.fit(
            x=train_x, y=[train_y for _ in range(self.num_losses)],
            batch_size=batch_size, epochs=epochs, verbose=1,
            callbacks=[model_checkpoint, TensorBoard(log_dir=log_dir)],
            validation_data=(val_x, [val_y for _ in range(self.num_losses)]))
        
    # Preprocessing

    def prep_features(self, locations_data,
                      with_labels=False, fit_binarizer=False):
        """Extract quantitative data, vectorized text, and labels.

        Arguments:
            locations_data: List of dicts 
            with_labels: boolean: To extract relevance labels
            fit_binarizer: boolean: To fit self.binarizer for conversion 
                between text and one-hot labeling.

        Returns: features as a dict of arrays, one_hot labels as an array
        """
        quants = np.array([self._prep_quants(d) for d in locations_data])
        mentions = np.array([self._prep_mentions(d) for d in locations_data])
        if with_labels:
            labels = [d['label'] for d in locations_data]
            print('Distribution of labels: {}\n'.format(Counter(labels)))
            if fit_binarizer:
                one_hots = np.array(self.binarizer.fit_transform(labels))
            else:
                one_hots = np.array(self.binarizer.transform(labels))
        else:
            one_hots = None
        features = {'quants': quants, 'mentions': mentions}
        return features, one_hots

    def _prep_quants(self, data):
        """Extract quantitative features from location data."""
        quants = [
            data.get('relevance', 0),
            len(data.get('mentions', [])),
            len(data.get('cluster', [])),
            data.get('cluster_ratio', 0)
        ]
        bounds = data.get('boundingbox', ())
        if bounds:
            quants.append(np.sqrt(_compute_area(bounds)))
        else:
            quants.append(0.0)
        return quants

    def _prep_mentions(self, data):
        """Extract and vectorize mentions."""
        mentions = data.get('mentions', [])
        if self.vectorizer:
            vectors = self.vectorizer.encode(mentions)
        else:
            vectors = []
        return vectors

def _compute_area(bounds):
    """Compute the area of geographic bounds.

    Argument bounds: decimal lat/lon coordinates in order
        (lower_left_lon, lower_left_lat, upper_right_lon, upper_right_lat)

    Returns: Area in km^2.
    """
    SQm_to_SQkm = 1e-6
    epsg_code = _get_utm_code(*bounds[:2])
    projector = pyproj.Proj(init='epsg:{}'.format(epsg_code))
    lowerleft = projector(*bounds[:2])
    upperright = projector(*bounds[2:])
    bbox = shapely.geometry.box(*lowerleft, *upperright)
    return bbox.area * SQm_to_SQkm
    
def _get_utm_code(lon, lat):
    """Compute the UTM EPSG zone code in which lon, lat fall."""
    basecode = 32601 if lat > 0 else 32701
    return basecode + int((180 + lon)/6.)

