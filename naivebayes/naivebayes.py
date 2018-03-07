"""Routines to train, save, restore, and run a binary multinomial Naive Bayes
classifier.

External classes:
    NBClassifier:  Wrapper to restore and run a multinomial naive-Bayes 
       classifier.
    NBTextClassifier: Descendant class with additional methods to
        classify text specifically.
    NBKeywordClassifier: Descendant class with methods to classify keywords.

External functions:
    train_model:  Train an NBClassifier instance from data and labels.
    train_from_dbs:  Train an NBClassifier instance from texts in databases.

Usage:
   To run the latest stored classifer, e.g. on a url:
   > nbc = NBTextClassifier()
   > nbc.predict_url(url)

   To train a model from databases (e.g. NEG_DB, POS_DB below):
   > nbc = train_from_dbs(neg_db=NEG_DB, pos_db=POS_DB, 
         x_val=5, material='text', freeze_dir=TEXT_MODEL_DIR)

"""

import datetime
import os
import sys

import pkg_resources
from sklearn.externals import joblib
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.naive_bayes import MultinomialNB

sys.path.append('../')
import config
import extract_text
import firebaseio
from naivebayes import curate_texts
from naivebayes import prep_text

TEXT_MODEL_DIR = pkg_resources.resource_filename(__name__, 'NBtext_models')
DEFAULT_MODEL_DIR = TEXT_MODEL_DIR
KW_MODEL_DIR = pkg_resources.resource_filename(__name__, 'NBkw_models')
LATEST_MODEL = 'latest_model.pkl'
DEFAULT_THRESHOLD = .7
POS_DB = firebaseio.DB(config.FIREBASE_GL_URL)
NEG_DB = firebaseio.DB(config.FIREBASE_NEG_URL)

class NBClassifier(object):
    """Wrapper to restore and run a multinomial naive-Bayes classifier.

    Attributes:
        vectorizer: an instance of a vectorizer (typically TfidfVectorizer
            from sklearn.feature_extraction.text, with all associated methods).
        classifier: an instance of a MultinomialNB classifier from
            from sklearn.naive_bayes, with all associated methods
        threshold: minimal accept probability for positive class 
        

    Methods:
        __call__:  Return probabilities that texts fall in positive class.

"""
    
    def __init__(self,
                 model_file='/'.join((DEFAULT_MODEL_DIR, LATEST_MODEL)),
                 vectorizer=None, classifier=None, threshold=None):
        if vectorizer is not None and classifier is not None:
            self.vectorizer = vectorizer
            self.classifier = classifier
            self.threshold = threshold
        else:
            try:
                self.vectorizer, self.classifier, self.threshold = joblib.load(
                    model_file)
            except FileNotFoundError:
                print('No saved classifier model found.')
                raise

    def __call__(self, texts):
        """Return probabilities that texts fall in positive class.

        Argument:  List of strings.

        Return:  List of probabilities.
        """
        vectors = self.vectorizer.transform(texts)
        probs = self.classifier.predict_proba(vectors)
        return probs[:,1]
    

class NBTextClassifier(NBClassifier):
    """Restores an NBClassifier model and provides addtional methods for
    classifying text.

    Additional methods:
        predict_url:  Run __call__ on text retrieved from single input url.
        classify_story:  Returns class and probability for text in a
            firebaseio.DBItem story record.
        predict_db_texts:  Run __call__ on all texts in a database.
    
    """
    
    def __init__(self, model_file='/'.join((TEXT_MODEL_DIR, LATEST_MODEL))):
        NBClassifier.__init__(self, model_file=model_file)
        
    def predict_url(self, url):
        """Return positive class probability for text retrieved from url."""
        text = extract_text.get_text(url)[0]
        prob = self.__call__([text])[0]
        return prob

    def classify_story(self, story, threshold=None):
        """Check class probability for story text against threshold.

        Returns 1 (0) if threshold is met (not met), along with probability.
        """
        if threshold is None:
            threshold = self.threshold
        try: 
            prob = self.__call__([story.record['text']])[0]
            classification = 1 if prob >= threshold else 0
        except KeyError as ke:
            print(ke)
            classification, prob = None, None
        except TypeError as te:
            print(te)
            classification = None
        return classification, prob
        
    def predict_db_texts(self, database):
        """Return probabilities for texts in a Firebase database.

        Returns: dict of text names and probabilities
        """
        names, texts = curate_texts.grab(database, material='text')
        probs = self.__call__(texts)
        predictions = {name:prob for name,prob in zip(names, probs)}
        return predictions

    
class NBKeywordClassifier(NBClassifier):
    """Restores an NBClassifier model and provides addtional methods for
    classifying keywords.

    Additonal methods:
        classify_story:  Returns class and probability for keywords in a
            firebaseio.DBItem story record.
    """
    
    def __init__(self, model_file='/'.join((KW_MODEL_DIR, LATEST_MODEL))):
        NBClassifier.__init__(self, model_file=model_file)

    def classify_story(self, story, threshold=None):
        """Check class probability for story text against threshold.

        Returns 1 (0) if threshold is met (not met), along with probability.
        """
        if threshold is None:
            threshold = self.threshold
        try: 
            prob = self.__call__([story.record['keywords']])[0]
            classification = 1 if prob >= threshold else 0
        except KeyError as ke:
            print(ke)
            classification, prob = None, None
        except TypeError as te:
            print(te)
            classification = None
        return classification, prob


def freeze_model(nbc, model_data, freeze_dir):
    """Pickle model and training data."""
    if not os.path.exists(freeze_dir):
        os.makedirs(freeze_dir)
    now = datetime.datetime.now().isoformat()
    modelfile = os.path.join(freeze_dir, now + 'model.pkl')
    datafile = os.path.join(freeze_dir, now + 'data.pkl')
    # temp: protocol=2 for back compatibility with python2.7
    joblib.dump((nbc.vectorizer, nbc.classifier, nbc.threshold),
                modelfile, protocol=2)
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

def train_from_dbs(neg_db=NEG_DB, pos_db=POS_DB, material='text',
                   x_val=5, threshold=DEFAULT_THRESHOLD, freeze_dir=None):
    """Train from our Firebase databases.

    Keyword arguments:
        material: 'texts' (and eventually (?) 'keywords', 'imagewords')
        x_val: integer k indicating k-fold cross-validation, or None
        freeze_dir: If given, the model will be pickled to disk in this dir.

    Returns an NBClassifier instance and cross-validation scores
    """
    neg = curate_texts.grab(neg_db, material=material)[1]
    pos = curate_texts.grab(pos_db)[1]
    data =  neg + pos
    labels = ([0 for _ in range(len(neg))] + [1 for _ in range(len(pos))])
    if material == 'text':
        vectors, vectorizer = prep_text.vectorize(data)
    classifier = MultinomialNB().fit(vectors, labels)
    nbc = NBClassifier(vectorizer=vectorizer, classifier=classifier,
                       threshold=threshold)
    if x_val is not None:
        scores = cross_val_score(MultinomialNB(), vectors, labels, cv=x_val)
    else:
        scores = None
    if freeze_dir is not None:
        model_data = {
            'data': data,
            'labels': labels,
            'cross_validation_scores': scores
        }
        freeze_model(nbc, model_data, freeze_dir)
    return nbc, scores


"""
# Future: If real testing becomes preferred to cross validation: 
# (random_state=0 provides the same shuffle every time)
test_frac = .1
train_vectors, test_vectors, train_labels, test_labels = train_test_split(
        vectors, labels, test_size=test_frac, random_state=0)
nbc = train_model(train_vectors, train_labels, vectorizer)
if test_vectors.shape[0] > 0:
        score = nbc.classifier.score(test_vectors, test_labels)
else:
    score = None
"""
