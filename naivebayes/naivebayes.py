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
from sklearn.naive_bayes import MultinomialNB

# TODO: better module handling
sys.path.append('../')
import curate_texts
import extract_text
import prep_text

MODEL_DIR = 'NBmodels'
LATEST_MODEL = 'latest_model.pkl'


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

    def predict_db_texts(self, database):
        """Return probability for all texts in a Firebase database."""
        names, texts = curate_texts.grab(database)
        probs = self.__call__(texts)
        return {name:prob for name,prob in zip(names, probs)}

    def classify_db_texts(self, database, threshold=.7):
        """Find texts meeting probability threshold in a Firebase database."""
        predictions = self.predict_db_texts(database)
        positives = {name:prob for name, prob in predictions.items()
                     if prob >= threshold}
        return positives
            
def train_model(data, labels, cross_validate=False, freeze_dir=None):
    """Train a binary mutltinomial naive-Bayes text classifier.

    Returns: An NBClassifer instance; if a freeze_dir is given, the
        model is additionally pickled to disk.
    """
    vectors, vectorizer = prep_text.vectorize(data)
    classifier = MultinomialNB().fit(vectors, labels)
    nbc = NBClassifier(vectorizer=vectorizer, classifier=classifier)
    if cross_validate:
        # TODO
        pass
    else:
        x_val_scores = None
    if freeze_dir is not None:
        freeze_model(nbc, data, labels, x_val_scores, freeze_dir)
    return nbc

def freeze_model(nbc, data, labels, x_val_scores, freeze_dir):
    """Pickle model and training data + cross validation scores."""
    if not os.path.exists(freeze_dir):
        os.makedirs(freeze_dir)
    now = datetime.datetime.now().isoformat()
    modelfile = os.path.join(freeze_dir, now + 'model.pkl')
    datafile = os.path.join(freeze_dir, now + 'data.pkl')
    joblib.dump((nbc.vectorizer, nbc.classifier), modelfile)
    joblib.dump((data, labels, x_val_scores), datafile)

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

def train_from_dbs(neg_db, pos_db,
                   cross_validate=False, freeze_dir='NBmodels'):
    """Train from our Firebase databases."""
    neg_texts = curate_texts.grab(neg_db)[1]
    pos_texts = curate_texts.grab(pos_db)[1]
    texts =  neg_texts + pos_texts
    labels = ([0 for _ in range(len(neg_texts))] +
              [1 for _ in range(len(pos_texts))])
    nbc = train_model(texts, labels,
                      cross_validate=cross_validate, freeze_dir=freeze_dir)
    return nbc

# TODO:  turn this into cross validation (using classifier.score method)
def test_model(train_data, train_targets, test_data, test_targets):
    """Test a Multinomial Naive Bayes text classifier.
    
    Returns: error rate on a labeled test dataset.
    """
    vecs, izer = get_vectors(train_data)
    classifier = MultinomialNB().fit(vecs, train_targets)
    test_vecs = izer.transform(test_data)
    preds = classifier.predict(test_vecs)
    return np.mean(preds == test_targets)
        


