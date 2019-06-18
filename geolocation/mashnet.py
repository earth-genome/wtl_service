"""Routines to train and run a classifier on relevance of geolocations.


"""
from collections import Counter
import datetime
from inspect import getsourcefile
import os
import sys

from keras.callbacks import ModelCheckpoint, TensorBoard
import numpy as np
import shapely
from sklearn.externals import joblib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelBinarizer

current_dir = os.path.dirname(os.path.abspath(getsourcefile(lambda:0)))
sys.path.insert(1, os.path.dirname(current_dir))
from geolocation.geolocate import MAX_MENTIONS
import sentence_encoder
from utilities.geobox import geobox

def tvt_split(locations_data, val_frac=.15, test_frac=.15, save_file=None):
    """Split locations_data into train, validation, and test sets."""
    reserve_frac = val_frac + test_frac
    train, reserved = train_test_split(locations_data, test_size=reserve_frac)
    val, test = train_test_split(reserved, test_size=test_frac/reserve_frac)
    splits = (train, val, test)
    if save_file:
        joblib.dump(splits, save_file)
    return splits

class MashNet(object):

    def __init__(self, model, session, binarizer=None, vectorizer=None):
        self.estimator = model
        self.num_losses = len(model.loss_functions)
        self.binarizer = binarizer if binarizer else LabelBinarizer()
        if vectorizer:
            self.vectorizer = vectorizer
        else:
            self.vectorizer = sentence_encoder.TFSentenceEncoder(
                session, pad_to=MAX_MENTIONS)

    #def __enter__(self):
    #    return self

    #def __exit__(self, exc_type, exc_value, traceback):
    #    self.session.close()

    def predict(self, locations_data):
        features, _ = self.prep_features(locations_data)
        probabilities = self.estimator.predict(features)
        return probabilities

    def predict_final(self, locations_data):
        if self.num_losses > 1:
            return self.predict(locations_data)[-1]
        else:
            return self.predict(locations_data)
    
    def predict_labels(self, locations_data):
        features, _ = self.prep_features(locations_data)
        probabilities = self.predict_final(features)
        labelings = []
        for loc_probs in probabilities:
            labeling = {c:p for c,p in zip(self.binarizer.classes_, loc_probs)}
            labelings.append(labeling)
        return labelings
    
    def pretty_predict(self, locations_data):
        output_labelings = self.predict_labels(locations_data)
        labels = [d.get('label') for d in locations_data]
        for label, output in zip(labels, output_labelings):
            print('Label: {}; prediction: {}'.format(label, output))

    def test(self, test_set):
        metrics = self.estimator.metrics_names
        test_x, test_y = self.prep_features(test_set, with_labels=True)
        evals = self.estimator.evaluate(
            test_x, [test_y for _ in range(self.num_losses)])
        return {m:e for m,e in zip(metrics, evals)}
        
    def train(self, train_set, val_set, batch_size=10, epochs=500):
        checkpt_prefix = os.path.join(
            os.path.dirname(os.path.abspath(getsourcefile(lambda:0))),
            'mashnet{}'.format(datetime.date.today().isoformat()))
        val_acc = 'val_' + self.estimator.metrics_names[-1]
        model_checkpoint = ModelCheckpoint(
            checkpt_prefix + '-Ep{epoch:02d}.hdf5',
            monitor=val_acc, verbose=1, period=int(epochs/10),
            save_best_only=True)
        train_x, train_y = self.prep_features(
            train_set, with_labels=True, fit_binarizer=True)
        val_x, val_y = self.prep_features(val_set, with_labels=True)                                         
        self.estimator.fit(
            x=train_x, y=[train_y for _ in range(self.num_losses)],
            batch_size=batch_size, epochs=epochs, verbose=1,
            callbacks=[model_checkpoint, TensorBoard()],
            validation_data=(val_x, [val_y for _ in range(self.num_losses)]))
        
    # Preprocessing

    def prep_features(self, locations_data,
                      with_labels=False, fit_binarizer=False):
        """Extract vector data, mentions, and labels from locations_data.

        Arguments:
            locations_data: List of dicts with at least a 'boundingbox'
            with_labels: boolean: To extract relevance labels
            fit_binarizer: boolean: To fit self.binarizer for conversion 
                between text and one-hot labeling.

        Returns: features as a dict of arrays, one_hot labels as an array
        """
        vectors = np.array([self._prep_vector(d) for d in locations_data])
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
        features = {'vectors': vectors, 'mentions': mentions}
        return features, one_hots

    def _prep_vector(self, data):
        """Extract quantitative features from location data."""
        vector = [
            data.get('relevance', 0),
            len(data.get('mentions', [])),
            len(data.get('cluster', [])),
            data.get('cluster_ratio', 0)
        ]
        try: 
            bbox = shapely.geometry.box(*data['boundingbox'])
            vector.append(np.mean(geobox.get_side_distances(bbox)))
        except KeyError as e:
            raise KeyError('Boundingbox size is required: {}'.format(repr(e)))
        return vector

    def _prep_mentions(self, data):
        mentions = data.get('mentions', '')
        vectors = self.vectorizer.encode(mentions)
        return vectors
