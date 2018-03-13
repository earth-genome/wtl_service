"""Routines to train, store, and run a binary multinomial Naive Bayes
classifier.

External classes:
    NBClassifier:  Wrapper to store and run a multinomial naive-Bayes 
       classifier.

External functions:
    train_from_dbs:  Train an NBClassifier instance from texts in databases.

Usage:
   To run the latest stored text classifer, e.g. on a url:
   > nbc = joblib.load('/'.join((TEXT_MODEL_DIR, 'latest_model.pkl')))
   > text = extract_text.get_text(url)[0]
   > nbc([text])

   To run on a DBItem story:
   > nbc.classify_story(story)

   To train a model from databases (e.g. NEG_DB, POS_DB below):
   > nbc = train_from_dbs(neg_db=NEG_DB, pos_db=POS_DB, 
         x_val=5, data_type='text', threshold=.7, freeze_dir=TEXT_MODEL_DIR)

"""

import sys

import pkg_resources
from sklearn.model_selection import cross_val_score
from sklearn.naive_bayes import MultinomialNB

sys.path.append('../')
import config
import extract_text
import firebaseio
from naivebayes import freezer
from naivebayes import prep_text
from naivebayes import prep_image


TEXT_MODEL_DIR = pkg_resources.resource_filename(__name__, 'NBtext_models')
IMAGE_MODEL_DIR = pkg_resources.resource_filename(__name__, 'NBimage_models')
DEFAULT_MODEL_DIR = TEXT_MODEL_DIR
POS_DB = firebaseio.DB(config.FIREBASE_GL_URL)
NEG_DB = firebaseio.DB(config.FIREBASE_NEG_URL)
DEFAULT_THRESHOLD = .65

class NBClassifier(object):
    """Wrapper to store and run a multinomial naive-Bayes classifier.

    Attributes:
        vectorizer: an instance of a vectorizer (typically TfidfVectorizer
            from sklearn.feature_extraction.text, with all associated methods).
        data_type: from secondary subheadings in firebase ('text', 'image',...)
            inferred from the relevant vectorizer (prep_text, prep_image,...)
        classifier: an instance of a MultinomialNB classifier from
            from sklearn.naive_bayes, with all associated methods
        threshold: minimal accept probability for positive class

    Methods:
        __call__:  Return probabilities that data fall in positive class.
        classify_story:  Returns class and probability for text in a
            firebaseio.DBItem story record.
        predict_db_data:  Run __call__ on all data of data_type in a database.

"""
    
    def __init__(self, vectorizer, classifier, threshold=None):
        
        self.vectorizer = vectorizer
        self.classifier = classifier
        self.threshold = threshold
        if type(self.vectorizer).__name__ == 'TfidfVectorizer':
            self.data_type = 'text'
        elif type(self.vectorizer).__name__ == 'ImageVectorizer':
            self.data_type = 'image'
        else:
            raise AttributeError('Vectorizer not recognized.')

    def __call__(self, data):
        """Return probabilities that data fall in positive class.

        Argument:  List of strings.

        Return:  List of probabilities.
        """
        vectors = self.vectorizer.transform(data)
        probs = self.classifier.predict_proba(vectors)
        return probs[:,1]

    def classify_story(self, story, threshold=None):
        """Check class probability for story against threshold.

        Returns 1 (0) if threshold is met (not met), along with probability.
        """
        if threshold is None:
            threshold = self.threshold
        try: 
            prob = self.__call__([story.record[self.data_type]])[0]
            classification = 1 if prob >= threshold else 0
        except KeyError as ke:
            print(ke)
            classification, prob = None, None
        except TypeError as te:
            print(te)
            classification = None
        return classification, prob
        
    def predict_db_data(self, database):
        """Return probabilities for data in a Firebase database.

        Returns: dict of text names and probabilities
        """
        names, data = database.grab_data(data_type=self.data_type)
        probs = self.__call__(data)
        predictions = {name:prob for name,prob in zip(names, probs)}
        return predictions


def train_from_dbs(neg_db=NEG_DB, pos_db=POS_DB, data_type='text',
                   x_val=5, threshold=DEFAULT_THRESHOLD, freeze_dir=None):
    """Train from our Firebase databases.

    Keyword arguments:
        data_type: 'text' (and eventually (?) 'image', 'keywords')
        x_val: integer k indicating k-fold cross-validation, or None
        freeze_dir: If given, the model will be pickled to disk in this dir.

    Returns an NBClassifier instance and cross-validation scores
    """
    neg = neg_db.grab_data(data_type=data_type)[1]
    pos = pos_db.grab_data(data_type=data_type)[1]
    data =  neg + pos
    labels = ([0 for _ in range(len(neg))] + [1 for _ in range(len(pos))])
    if data_type == 'text':
        vectors, vectorizer = prep_text.vectorize(data)
    else:
        return None, None
    classifier = MultinomialNB().fit(vectors, labels)
    nbc = NBClassifier(vectorizer, classifier, threshold=threshold)
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
        freezer.freeze_model(nbc, model_data, freeze_dir)
    return nbc, scores


"""
# Future: If real testing becomes preferred to cross validation: 
# (random_state=0 provides the same shuffle every time)
from sklearn.model_selection import train_test_split
test_frac = .1
train_vectors, test_vectors, train_labels, test_labels = train_test_split(
        vectors, labels, test_size=test_frac, random_state=0)
nbc = train_model(train_vectors, train_labels, vectorizer)
if test_vectors.shape[0] > 0:
        score = nbc.classifier.score(test_vectors, test_labels)
else:
    score = None
"""
