"""Ad hoc scripts to restore and run text classification models.

Usage: 
tourism_oracle = Oracle(*load(model_name, model_dir))
clf, label = tourism_oracle('My long story about good places to visit.')

It is expected that the model is saved as a *.hdf5 file, with a correspondingly named *.txt file containing text labels, one label per line. 

"""

import glob
from inspect import getsourcefile
import os
import re

import numpy as np
from sklearn.externals import joblib
from tensorflow.keras.models import load_model

pwd = os.path.dirname(os.path.abspath(getsourcefile(lambda:0)))
VECTORIZER_FILE = os.path.join(pwd, 'vectorizer_1.pkl')

def load(model_name, model_dir, vectorizer_file=VECTORIZER_FILE):
    """Load vectorizer, model, and labels."""
    vectorizer = joblib.load(vectorizer_file)
    model = load_model(os.path.join(model_dir, model_name + '.hdf5'))
    label_path = os.path.join(model_dir, model_name + '.txt')
    with open(label_path) as f:
        labels = [l.strip() for l in f]
    return vectorizer, model, labels

class Oracle(object):
    """Class to run text classification models.

    Attributes:
        vectorizer: reloaded text vectorizer
        model: reloaded Keras model
        labels: list of text labels associated to model output
    
    External methods:
        __call__: Determine most probable class and label for text.
        predict_class: Determine most probable (integer) class for text.
        predict_label: Run model prediction and extract most probable label.
    """
    
    def __init__(self, vectorizer, model, labels):
        self.vectorizer = vectorizer
        self.model = model 
        self.labels = labels 

    def __call__(self, text):
        """Determine most probable class and label for text.

        Returns: Class (int) and dict of form {label: prob}
        """
        probs = self._predict(text)
        # Cast types to make output JSON-serializable
        argmax = int(np.argmax(probs))
        return argmax, {self.labels[argmax]: float(probs[argmax])}

    def predict_class(self, text):
        """Determine most probable (integer) class for text."""
        return self.__call__(text)[0]

    def predict_best_label(self, text):
        """Determine most probable label for text.

        Returns: dict of form {label: prob}
        """
        return self.__call__(text)[1]

    def predict_labels(self, text):
        """Predict and attach labels for a single text."""
        probs = self._predict(text)
        return {l: float(p) for l,p in zip(self.labels, probs)}
        
    def _predict(self, text):
        """Run model prediction on a single text."""
        return next(iter(self._predict_batch([text])))
        
    def _predict_batch(self, texts):
        """Run model prediction on multiple texts."""
        vectors = self.vectorizer.transform(texts).toarray()
        return self.model.predict(vectors)
