"""Routines to train, store, and run a bag-of-words classifier.

Essentially this bundles vectorizer and classifier in one framework
and provides methods to store, reload, and run on news stories stored
in our Firebase databases, with structure defined in firebasio.

Vectorizers include TfidfVectorizer or the custom ImageVectorizer, with
usage defined in modules prep_text and prep_image.

Supported classifiers include sklearn classes MultinomialNB,
LogisticRegression, and MLPClassifier, or a mutliclass option such as
OneVsRestClassifier(MLPClassifier(activation='logistic', solver='lbfgs')),
requiring fit() and predict_proba() methods.

Classes:
    BoWClassifier:  Train, store, and run a bag-of-words classifier.
    BinaryBoWClassifier: BowClassifier descendant for binary classification.

Usage:
   To train a binary MultinomailNB text model from databases (e.g. NEG_DB, POS_DB
   below), given a path TEXT_MODEL_DIR to save the model:
   > from sklearn.naive_bayes import MultinomialNB()
   > nbc = BinaryBoWClassifier(MultinomailNB(), 'text')
   > nbc.train_from_dbs(neg_db=NEG_DB, pos_db=POS_DB, threshold=.7,
                        x_val=5, freeze_dir=TEXT_MODEL_DIR)

   To run the latest stored text classifer, e.g. on a url:
   > from sklearn.externals import joblib
   > import extract_text
   > nbc = joblib.load('/'.join((TEXT_MODEL_DIR, 'latest_model.pkl')))
   > text = extract_text.get_text(url)[0]
   > nbc.predict_datum(text)

   To run on a DBItem story:
   > nbc.classify_story(story)

"""

from sklearn.model_selection import cross_val_score

from bagofwords import freezer
from bagofwords import prep_text
from bagofwords import prep_image
from utilities import firebaseio

POS_DB = firebaseio.DB(firebaseio.FIREBASE_GL_URL)
NEG_DB = firebaseio.DB(firebaseio.FIREBASE_NEG_URL)

DATA_TYPES = ('text', 'image_tags')

class BoWClassifier(object):
    """Train, store, and run a bag-of-words classifier.

    Attributes:
        estimator: E.g. MultinomailNB(), LogisticRegression(),
            MLPClassifier(activation='logistic', solver='lbfgs'),
            or mutliclass option such as
            OneVsRestClassifier(MLPClassifier(
                activation='logistic', solver='lbfgs'))
            Must implement fit() and predict_proba() methods.
        data_type: from allowed DATA_TYPES, defines the relevant vectorizer

    Attributes set during training:
        vectorizer: a TfidfVectorizer or custom ImageVectorizer from prep_image 
        threshold: probability threshold 
        scores (optional): cross validation scores
        

    External methods:
        predict_data: Determine probabilities for input data.
        predict_datum: Determine probabilities for input datum (singular).
        predict_db: Determine probabilities for data in a Firebase database.
        predict_story: Determine probabilities for a Firebase story.
        classify_story:  Determine class(es) for story.
        train: Build vectors and fit model.
        freeze: Pickle model and data.
        train_from_dbs: Train from our Firebase databases, with option to
            freeze.
"""
    
    def __init__(self, estimator, data_type):
        self.estimator = estimator
        if data_type in DATA_TYPES:
            self.data_type = data_type
        else:
            raise ValueError('data_type must be from: {}.'.format(DATA_TYPES))

    def __call__(self, data):
        """Private method: determine probabilities for input data.

        Argument data: List of strings or dicts (input to self.vectorizer)
            
        Returns: Array of class probabilities.
        """
        vectors = self.vectorizer.transform(data)
        return self.estimator.predict_proba(vectors)

    def predict_data(self, data):
        """Determine probabilities for input data."""
        return self.__call__(data)

    def predict_datum(self, datum):
        """Determine probabilities for input datum (singular)."""
        return self.__call__([datum])[0]
        
    def predict_db(self, database):
        """Determine probabilities for data in a Firebase database.

        Returns: dict of text index and class probabilities
        """
        idx, data = database.grab_data(data_type=self.data_type)
        probs = self.__call__(data)
        return dict(zip(idx, probs))

    def predict_story(self, story):
        """Determine probabilities for a Firebase story."""
        try: 
            probs = self.__call__([story.record[self.data_type]])[0]
        except KeyError:
            try:
                probs = self.__call__(
                    [firebaseio.EMPTY_DATA_VALUES[self.data_type]])[0]
            except KeyError:
                print('Firebaseio: No EMPTY_DATA_VALUE assigned.\n')
                raise
        return probs

    def classify_story(self, story):
        """Determine class(es) for story.

        Returns: Integer class labels, along with associated probabilities.
        """
        probs = self.predict_story(story)
        membership = (probs >= self.threshold).astype(int)
        return list(zip(membership, probs))

    def train(self, data, labels, threshold=.5, x_val=5):
        """Build vectors and fit model."""
        self.threshold = threshold
        
        if self.data_type == 'text':
            vectors, self.vectorizer = prep_text.build_vectorizer(data)
        elif self.data_type == 'image_tags':
            vectors, self.vectorizer = prep_image.build_vectorizer(data)
        self.estimator.fit(vectors, labels)
        
        if x_val:
            self.scores = cross_val_score(self.estimator, vectors, labels,
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

    def train_from_dbs(self, neg_db=NEG_DB, pos_db=POS_DB,
                       threshold=.5, x_val=5, freeze_dir=None):
        """Train from our Firebase databases, with option to freeze model.

        Arguments:
            neg_db, pos_db: firebaseio.DB instances
            threshold: probabilty threshold 
            x_val: integer k indicating k-fold cross-validation, or None
            freeze_dir: If given, the model will be pickled to this directory
        """
        neg = neg_db.grab_data(data_type=self.data_type)[1]
        pos = pos_db.grab_data(data_type=self.data_type)[1]
        data =  neg + pos
        labels = ([0 for _ in range(len(neg))] + [1 for _ in range(len(pos))])
        self.train(data, labels, threshold=threshold, x_val=x_val)
        
        if freeze_dir:
            self.freeze(freeze_dir, data=data, labels=labels)
        return self


class BinaryBoWClassifier(BoWClassifier):
    """BoWClassifier descendant for binary classification.

    Returns probabilities / classifications for positive class only.
    """
    def __init__(self, estimator, data_type):
        super().__init__(estimator, data_type)

    def predict_data(self, data):
        return super().predict_data(data)[:,1]

    def predict_datum(self, datum):
        return super().predict_datum(datum)[1]

    def predict_db(self, database):
        predictions = super().predict_db(database)
        return {idx:probs[1] for idx, probs in predictions.items()}

    def predict_story(self, story):
        return super().predict_story(story)[1]

    # Since we've overwritten predict_story, rebuild this routine instead
    # of calling super().classify_story:
    def classify_story(self, story):
        prob = self.predict_story(story)
        membership = 1 if prob >= self.threshold else 0
        return membership, prob


    


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
