"""Routine to pickle sklearn classifiers from the local naivebayes package.

Classifier instances frozen with this routine can be restored directly:
clf = joblib.load('/path/to/latest_model.pkl')
"""

import datetime
import os

from sklearn.externals import joblib

LATEST_MODEL = 'latest_model.pkl'

def freeze_model(clf, model_data, freeze_dir):
    """Pickle model and training data."""
    if not os.path.exists(freeze_dir):
        os.makedirs(freeze_dir)
    now = datetime.datetime.now().isoformat()
    modelfile = os.path.join(freeze_dir, now + 'model.pkl')
    datafile = os.path.join(freeze_dir, now + 'data.pkl')
    # temp: protocol=2 for back compatibility with python2.7
    joblib.dump(clf, modelfile, protocol=2)
    joblib.dump(model_data, datafile, protocol=2)

    # reset symlink LATEST_MODEL to point to current model
    latest = os.path.join(freeze_dir, LATEST_MODEL)
    filenames = []
    for dir_, _, files in os.walk(freeze_dir):
        for filename in files:
            if 'model' in filename:
                filenames.append(filename)
    if LATEST_MODEL in filenames:
        filenames.remove(LATEST_MODEL)
        os.unlink(latest)
    filenames.sort(reverse=True)
    os.symlink(filenames[0], latest)
    return
