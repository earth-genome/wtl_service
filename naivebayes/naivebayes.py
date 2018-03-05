"""Routines to train, save, restore, and run a binary multinomial Naive Bayes
text classifier.

External class:
    NBClassifier:  Wrapper to restore and run a multinomial naive-Bayes text
       classifier.

    Attributes:
        vectorizer: an instance of a vectorizer (typically TfidfVectorizer)
            from sklearn.feature_extraction.text, with all associated methods.
        classifier: an instance of a MultinomialNB classifier from
            from sklearn.naive_bayes, with all associated methods

    Methods:
        __call__:  Return probabilities that texts fall in positive class.
        predict_url:  Run __call__ on text retrieved from single input url.
        predict_db_texts:  Run __call__ on all texts in a database.
        classify_db_texts:  Return texts that meet a threshold probability.

External functions:
    train_model:  Train an NBClassifier instance from data and labels.
    train_from_dbs:  Train an NBClassifier instance from texts in databases.


Usage:
   To run the latest stored classifer, e.g. on a url:
   > nbc = NBClassifier()
   > nbc.predict_url(url)

   To run on all stories from newsapi_scraper.py for today, with
   database instantiated as STORY_SEEDS (e.g. curate_texts.STORY_SEEDS)
   > curate_texts.upload(STORY_SEEDS)
   > positives = nbc.classify_db_texts(STORY_SEEDS)
   # At the end of the day:
   > curate_texts.clear_all(STORY_SEEDS)

   To train a model from databases instantiated as NEGATIVE_TRAINING_CASES
   and GOOD_LOCATIONS (e.g. via curate_texts)
   > nbc = train_from_dbs(NEGATIVE_TRAINING_CASES, GOOD_LOCATIONS)

"""

import datetime
import os
import sys

from sklearn.externals import joblib
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB

# TODO: better module handling
sys.path.append('../')
import curate_texts
import extract_text
import prep_text

import pdb

MODEL_DIR = 'NBmodels'
LATEST_MODEL = 'latest_model.pkl'
POS_DB = curate_texts.GOOD_LOCATIONS
NEG_DB = curate_texts.NEGATIVE_TRAINING_CASES


class NBClassifier(object):
    """Wrapper to restore and run a multinomial naive-Bayes text classifier.

    Attributes:
        vectorizer: an instance of a vectorizer (typically TfidfVectorizer)
            from sklearn.feature_extraction.text, with all associated methods.
        classifier: an instance of a MultinomialNB classifier from
            from sklearn.naive_bayes, with all associated methods

    Methods:
        __call__:  Return probabilities that texts fall in positive class.
        predict_url:  Run __call__ on text retrieved from single input url.
        predict_db_texts:  Run __call__ on all texts in a database.
        classify_db_texts:  Return texts that meet a threshold probability.

"""
    
    def __init__(self, model_file=os.path.join(MODEL_DIR, LATEST_MODEL),
                 vectorizer=None, classifier=None):
        if vectorizer is not None and classifier is not None:
            self.vectorizer = vectorizer
            self.classifier = classifier
        else:
            try:
                self.vectorizer, self.classifier = joblib.load(model_file)
            except FileNotFoundError:
                print('No saved model found.')
                raise

    def __call__(self, texts):
        """Return probabilities that texts fall in positive class.

        Argument:  List of strings.

        Return:  List of probabilities.
        """
        vectors = self.vectorizer.transform(texts)
        probs = self.classifier.predict_proba(vectors)
        return probs[:,1]

    def predict_url(self, url):
        """Return positive class probability for text retrieved from url."""
        chunks = extract_text.get_text(url)
        text = ' '.join(chunks)
        prob = self.__call__([text])[0]
        return prob

    def predict_db_texts(self, database, threshold=None):
        """Return probabilities for texts in a Firebase database.

        Keyword argument:
            threshold: If given, only those texts with probabilities greater
            than threshold are returned (None or float in [0,1)).

        Returns: dict of text names and probabilities
        """
        names, texts = curate_texts.grab(database)
        probs = self.__call__(texts)
        predictions = {name:prob for name,prob in zip(names, probs)}
        if threshold is not None:
            predictions = {
                name:prob for name, prob in predictions.items()
                if prob >= threshold
            }
        return predictions
            
def train_model(vectors, labels, vectorizer):
    """Train a binary mutltinomial naive-Bayes classifier.

    Returns: An NBClassifer instance
    """
    classifier = MultinomialNB().fit(vectors, labels)
    nbc = NBClassifier(vectorizer=vectorizer, classifier=classifier)
    return nbc

def freeze_model(nbc, model_data, freeze_dir):
    """Pickle model and training data."""
    if not os.path.exists(freeze_dir):
        os.makedirs(freeze_dir)
    now = datetime.datetime.now().isoformat()
    modelfile = os.path.join(freeze_dir, now + 'model.pkl')
    datafile = os.path.join(freeze_dir, now + 'data.pkl')
    # temp: protocol=2 for back compatibility with python2.7
    joblib.dump((nbc.vectorizer, nbc.classifier), modelfile, protocol=2)
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

def train_from_dbs(neg_db=NEG_DB, pos_db=POS_DB, category='/texts',
                   test_frac=0, freeze_dir=MODEL_DIR):
    """Train from our Firebase databases.

    Keyword arguments:
        dbcat: '/texts' (and eventually (?) '/keywords', '/imagewords')
        test_frac: Fraction of data to be reserved for testing (default 0).
        freeze_dir: If given, the model will be pickled to disk in this dir.

    Returns an NBClassifier instance and test_score
    """
    neg_texts = curate_texts.grab(neg_db, category)[1]
    pos_texts = curate_texts.grab(pos_db, category)[1]
    texts =  neg_texts + pos_texts
    labels = ([0 for _ in range(len(neg_texts))] +
              [1 for _ in range(len(pos_texts))])
    if category == '/texts':
        vectors, vectorizer = prep_text.vectorize(texts)
    # random_state=0 provides the same shuffle every time 
    train_vectors, test_vectors, train_labels, test_labels = train_test_split(
            vectors, labels, test_size=test_frac, random_state=0)
    nbc = train_model(train_vectors, train_labels, vectorizer)
    if test_vectors.shape[0] > 0:
        score = nbc.classifier.score(test_vectors, test_labels)
    else:
        score = None
    if freeze_dir is not None:
        model_data = {
            'texts': texts,
            'labels': labels,
            'train_data': (train_vectors, train_labels),
            'test_data': (test_vectors, test_labels),
            'test_score': score
        }
        freeze_model(nbc, model_data, freeze_dir)
    return nbc, score

        


