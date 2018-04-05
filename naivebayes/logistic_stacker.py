"""Routines to train, store, and run logistic regression on top of the output
of other classifiers.

External class:
    LogisticStacker:  Wrapper to store and run a logistic regression
        stacking classifier.

External function:
    train_from_dbs:  Train a LogisticStacker instance from database stories
        and input classifiers.

Usage:    
    To train on output from Naive Bayes text and image classifiers:
    > from sklearn.externals import joblib
    > from naivebayes.naivebayes import TEXT_MODEL_DIR, IMAGE_MODEL_DIR
    > nbtext = joblib.load('/'.join((TEXT_MODEL_DIR, 'latest_model.pkl')))
    > nbimage = joblib.load('/'.join((IMAGE_MODEL_DIR, 'latest_model.pkl')))
    > logstack, scores = train_from_dbs(
          nbtext, nbimage,
          neg_db=NEG_DB, pos_db=POS_DB, 
          x_val=5, threshold=.7,
          freeze_dir=STACKER_MODEL_DIR
      )

    To classify a DBItem story:
    > logstack.classify_story(story)

    To restore and run on a url:
    > from sklearn.externals import joblib
    > import extract_text
    > import firebaseio
    > logstack = joblib.load('/'.join((STACKER_MODEL_DIR,
                             'latest_model.pkl')))
    > record = {'url': url}
    > record.update(extract_text.get_parsed_text(url))
    > story = firebaseio.DBItem('/null', None, record)
    > logstack([story])
    
"""

import json
import numpy as np
import sys

import pkg_resources
from sklearn.model_selection import cross_val_score
from sklearn.linear_model import LogisticRegression

sys.path.append('../')
import config
import firebaseio
from naivebayes import freezer

STACKER_MODEL_DIR = pkg_resources.resource_filename(
    __name__, 'Stacker_models'
)
POS_DB = firebaseio.DB(config.FIREBASE_GL_URL)
NEG_DB = firebaseio.DB(config.FIREBASE_NEG_URL)
DEFAULT_THRESHOLD = .65

# Until image traning database sufficiently samples possible tag words,
# we will hand tune relative text / image weights:
HAND_TUNE_PARAMS = np.array([.9, .1])

class LogisticStacker(object):
    """Wrapper to restore and run a logistic regression stacking
    classifier.

    Attributes:
        input_classifiers: list of classifiers (e.g. instances of
            naivebayes.NBClassifer()), each of whose outputs is to
            be an input feature for the stacker.
        stacker: an instance of a LogisticRegression classifier from
            from sklearn.linear_model, with all associated methods
        threshold: minimal accept probability for positive class

    Methods:
        __call__:  Return probabilities that firebaseio.DBItem stories
            fall in positive class.
        classify_story:  Returns class and probability for a story
        predict_db_stories:  Run __call__ on all stories in a database.

"""

    def __init__(self, stacker, *input_classifiers, threshold=None):
        
        self.input_classifiers = input_classifiers
        self.stacker = stacker
        self.threshold = threshold

    def __call__(self, stories):
        features = [[ic.classify_story(s)[1] for ic in self.input_classifiers]
                    for s in stories]
        features = np.array(features)
        probs = self.stacker.predict_proba(features)
        return probs[:,1]

    def classify_story(self, story):
        """Check class probability for story against self.threshold.

        Returns 1 (0) if threshold is met (not met), along with probability.
        """
        prob = self.__call__([story])[0]
        if self.threshold is not None:
            classification = 1 if prob >= self.threshold else 0
        else:
            classification = None
        return classification, prob    
        
    def predict_db_data(self, database):
        """Return probabilities for data in a Firebase database.

        Returns: dict of text names and probabilities
        """
        stories = database.grab_stories()
        probs = self.__call__(stories)
        predictions = {story.idx:prob for story,prob in zip(stories, probs)}
        return predictions


def train_from_dbs(*input_classifiers,
                   neg_db=NEG_DB, pos_db=POS_DB, 
                   x_val=5,
                   threshold=DEFAULT_THRESHOLD,
                   hand_tune_params=None, 
                   freeze_dir=None):
    """Train from our Firebase databases.

    Keyword arguments:
        x_val: integer k indicating k-fold cross-validation, or None
        hand_tune_params: np.array of relative weights for input_classifiers,
            or None
        freeze_dir: If given, the model will be pickled to disk in this dir.

    Returns a LogisticRegression instance and cross-validation scores
    """
    neg = neg_db.grab_stories()
    pos = pos_db.grab_stories()
    stories =  neg + pos
    labels = ([0 for _ in range(len(neg))] + [1 for _ in range(len(pos))])
    features = [[ic.classify_story(s)[1] for ic in input_classifiers]
                    for s in stories]
    features = np.array(features)
    stacker = LogisticRegression(verbose=1).fit(features, labels)

    # Hand tuning:
    if hand_tune_params:
        assert len(hand_tune_params) == len(input_classifiers)
        totalweight = np.sum(stacker.coef_)
        stacker.coef_ = np.array([hand_tune_params*totalweight])

    # x_val only functions correctly without hand tuning:
    if x_val:
        scores = cross_val_score(LogisticRegression(), features, labels,
                                 cv=x_val)
    else:
        scores = None
        
    logstack = LogisticStacker(stacker,
                               *input_classifiers,
                               threshold=threshold)
    if freeze_dir:
        model_data = {
            'data': json.dumps({s.idx:s.record for s in stories}, indent=4),
            'labels': labels,
            'cross_validation_scores': scores
        }
        freezer.freeze_model(logstack, model_data, freeze_dir)
    return logstack, scores
