"""Ad hoc script to restore the model in this directory."""

from inspect import getsourcefile
import os
import sys

from sklearn.externals import joblib
import tensorflow as tf

from geoloc_model import sentence_encoder

current_dir = os.path.dirname(os.path.abspath(getsourcefile(lambda:0)))
models_dir = os.path.dirname(current_dir)

def restore():
    """Ad hoc rebuild of a saved MashNet. Paths to files are hardcoded.

    Returns: MashNet and TensorFlow Graph instances.
    """
    graph = tf.Graph()
    with graph.as_default():
        net = joblib.load(
            os.path.join(current_dir, 'mashnet-128hidden-2019-07-03.pkl'))
        net.estimator = tf.keras.models.load_model(
            os.path.join(current_dir, 'ChkPtEp257.hdf5'))

    net.vectorizer = sentence_encoder.TFSentenceEncoder(
        tf.Session(),
        module_path=os.path.join(models_dir, 'universal_sentence_encoder',
              '1fb57c3ffe1a38479233ee9853ddd7a8ac8a8c47'),
        pad_to=6)
    return net, graph
