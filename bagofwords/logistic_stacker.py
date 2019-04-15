"""Routines to train, store, and run logistic regression on top of the output
of other classifiers.

This code is substantially copied from bagofwords.py, specialized to
build features from the output of instances of BinaryBoWClassifier models and
operate on our Firebase stories as input.  

This was built assuming sklearn LogisticRegression() as the estimator but
should generatlize to other sklearn classifiers with fit() and predict_proba()
methods.

External class: Stacker

Usage:    
    To train on BinaryBoWClassifier instances nbtext and nbimage using
    stories from our default databases:
    > from sklearn.linear_model import LogisticRegression
    > lstack = BinaryStacker(LogisticRegression(), nbtext, nbimage)
    > lstack.train_from_dbs(
          threshold=.7,
          hand_tune_params=HAND_TUNE_PARAMS,
          freeze_dir='/path/to/model/dir')
    (See train_from_dbs() below for default database parameters.)

    To classify a DBItem story:
    > lstack.classify_story(story)

    To restore and run on a url:
    > from sklearn.externals import joblib
    > import extract_text
    > import firebaseio
    > lstack = joblib.load('/'.join(('/path/to/model/dir', 'latest_model.pkl')))
    > record = {'url': url}
    > record.update(extract_text.get_parsed_text(url))
    > story = firebaseio.DBItem('/null', None, record)
    > lstack.classify_story(story)

Note: As written, this module functions only with BinaryBoWClassifier
instances, because single value (not array) output is expected from
predict_story() in building features from the outputs of the input_classifiers:
    features = [[ic.predict_story(s) for ic in self.input_classifiers]
                for s in stories]
"""

import json
import numpy as np

from sklearn.model_selection import cross_val_score

from bagofwords import freezer
from utilities import firebaseio

# Until image traning database sufficiently samples possible tag words,
# we will hand tune relative text / image weights:
HAND_TUNE_PARAMS = np.array([.9, .1])

class Stacker(object):
    """Train, story and run a logistic regression stacking classifier.

    Attributes:
        estimator: typically an instance of sklearn LogisticRegression()
        input_classifiers: list of classifiers (e.g. instances of
            naivebayes.NBClassifer()), each of whose outputs is to
            be an input feature for the stacker.
            
    Attributes set during training:
        threshold: probability threshold 
        scores (optional): cross validation scores

    External methods:
        predict_stories: Determine probabilities for input stories.
        predict_story: Determine probabilities for input story (singular).
        classify_story:  Determine class(es) for story.
        predict_db: Determine probabilities for data in a Firebase database.
        train: Build vectors and fit model.
        freeze: Pickle model and data.
        train_from_dbs: Train from our Firebase databases, with option to
            freeze.
"""

    def __init__(self, estimator, *input_classifiers):
        self.estimator = estimator
        self.input_classifiers = input_classifiers

    def __call__(self, stories):
        """Private method: determine probabilities for input stories.
        
        Returns: Array of class probabilities.
        """
        features = [[ic.predict_story(s) for ic in self.input_classifiers]
                    for s in stories]
        return self.estimator.predict_proba(np.array(features))

    def predict_stories(self, stories):
        """Determine probabilities for input stories."""
        return self.__call__(stories)

    def predict_story(self, story):
        """Determine probabilities for input story (singular)."""
        return self.__call__([story])[0]

    def classify_story(self, story):
        """Determine class(es) for story.

        Returns: Integer class labels, along with associated probabilities.
        """
        probs = self.predict_story(story)
        membership = (probs >= self.threshold).astype(int)
        return list(zip(membership, probs))

    def predict_db(self, database, category):
        """Return probabilities for data in a Firebase database.

        Returns: dict of text names and probabilities
        """
        stories = database.grab_stories(category)
        probs = self.__call__(stories)
        predictions = {story.idx:prob for story,prob in zip(stories, probs)}
        return predictions

    def train(self, stories, labels, threshold=.5, x_val=5):
        """Build vectors and fit model."""
        self.threshold = threshold

        features = [[ic.predict_story(s) for ic in self.input_classifiers]
                    for s in stories]
        self.estimator.fit(np.array(features), labels)

        # Achtung! x_val runs before any hand tuning (and in incompatible
        # with hand tuning)
        if x_val:
            self.scores = cross_val_score(self.estimator, features, labels,
                                          cv=x_val)
        return self

    def freeze(self, freeze_dir, **model_data):
        """Pickle model and data."""
        try:
            model_data.update({'cross_validation_scores': self.scores})
        except AttributeError:
            pass
        freezer.freeze_model(self, model_data, freeze_dir)
        return

    def train_from_dbs(
        self,
        neg_db=firebaseio.DB(**firebaseio.FIREBASES['negative-training-cases']),
        pos_db=firebaseio.DB(**firebaseio.FIREBASES['good-locations']),
        category='/stories',
        threshold=.5,
        x_val=5,
        hand_tune_params=None, 
        freeze_dir=None):
        """Train from our Firebase databases.

        Arguments:
            neg_db, pos_db: firebaseio.DB instances
            category: top-level database key
            threshold: probabilty threshold 
            x_val: integer k indicating k-fold cross-validation, or None
            hand_tune_params: array of relative weights for input_classifiers
            freeze_dir: If given, the model will be pickled to this directory
        """
        neg = neg_db.grab_stories(category)
        pos = pos_db.grab_stories(category)
        stories =  neg + pos
        labels = ([0 for _ in range(len(neg))] + [1 for _ in range(len(pos))])
        self.train(stories, labels, threshold=threshold, x_val=x_val)

        if hand_tune_params is not None:
            if len(hand_tune_params) != len(self.input_classifiers):
                raise ValueError('Tuning params not matched to classifiers.')
            totalweight = np.sum(self.estimator.coef_)
            self.estimator.coef_ = np.array([hand_tune_params*totalweight])

        if freeze_dir:
            data = json.dumps({s.idx:s.record['url'] for s in stories},
                              indent=4)
            self.freeze(freeze_dir, data=data, labels=labels)
                        
        return self

class BinaryStacker(Stacker):
    """Stacker descendant for binary classification.

    Returns probabilities / classifications for positive class only.
    """
    def __init__(self, estimator, *input_classifiers):
        super().__init__(estimator, *input_classifiers)

    def predict_stories(self, stories):
        return super().predict_stories(stories)[:,1]

    def predict_story(self, story):
        return super().predict_story(story)[1]

    def predict_db(self, database, category):
        predictions = super().predict_db(database, category)
        return {idx:probs[1] for idx, probs in predictions.items()}

    # Since we've overwritten predict_story, rebuild this routine instead
    # of calling super().classify_story:
    def classify_story(self, story):
        prob = self.predict_story(story)
        membership = 1 if prob >= self.threshold else 0
        return membership, prob
