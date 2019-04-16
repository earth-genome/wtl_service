"""Routines to train, store, and run a bag-of-words classifier for text themes.

Class: ThemeClassifier

This class descends from bagofwords.BoWClassifier, specializing as follows:
-- A default estimator (sklearn MLPClassifier) is proposed in __init__
-- The data_type is fixed to 'text'
-- Training happens only on a single database (defaults to 'good-locations')
-- Methods are provided to extract string themes from the output vector
    probabilities provided by BoWClassifier methods

To train with defaults:
tc = ThemeClassifier()
tc.train_from_dbs(freeze_dir='/path/to/save/model')

To get themes for a DBItem story:
themes = tc.predict_story_themes(story)


"""

from collections import Counter
from sklearn.multiclass import OneVsRestClassifier 
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import MultiLabelBinarizer

from bagofwords import bagofwords
from utilities import firebaseio

THRESHOLD = .1
    
class ThemeClassifier(bagofwords.BoWClassifier):
    """BoW descendant to classify text themes.

    Descendant attributes:
        themes:  Dict of known themes and their corresponding vector indices
        themesinv:  The inverse dictionary

    Descendant external methods:
        predict_text_themes: Get theme(s) and their probabilities for a text.
        predict_story_themes: Get theme(s) and their probabilities for a story.
        train_from_db: Train from our Firebase database, with option to
            freeze model (overwrites parent method).  
    """
    def __init__(self, estimator=None):
        if not estimator:
            estimator = OneVsRestClassifier(
                MLPClassifier(
                    hidden_layer_sizes=(100,),
                    activation='logistic',
                    solver='lbfgs',
                    warm_start=True,
                    verbose=True))
        super().__init__(estimator, data_type='text')
        
    def predict_text_themes(self, text):
        """Determine theme(s) and their probabilities for a text."""
        probs = self.predict_datum(text)
        return self._extract_themes(probs)

    def predict_story_themes(self, story):
        """Determine theme(s) and their probabilities for a story."""
        probs = self.predict_story(story)
        return self._extract_themes(probs)

    def train_from_dbs(self, database='good-locations', threshold=THRESHOLD,
                       x_val=None, freeze_dir=None):
        """Train from our Firebase database, with option to freeze model.

        Arguments:
            database: named database, from firebaseio.FIREBASES
            threshold: probabilty threshold 
            x_val: integer k indicating k-fold cross-validation, or None
            freeze_dir: If given, the model will be pickled to this directory
        """
        db_client = firebaseio.DB(database)
        stories = db_client.grab_stories()
        texts = [s.record['text'] for s in stories]
        labels = [s.record['themes'] if 'themes' in s.record.keys() else []
                  for s in stories]
        self = self._gather_themes(labels)
        labelbins = self._binarize(labels)

        self.train(texts, labelbins, threshold=threshold, x_val=x_val)
        if freeze_dir:
            self.freeze(freeze_dir, data=texts, labels=labels, counts=counts)
        return self

    def _binarize(self, labels):
        """Convert labels to multi-hot encoding."""
        labelints = [[self.themes[c] for c in l] for l in labels]
        labelbins = MultiLabelBinarizer().fit_transform(labelints)
        return labelbins

    def _gather_themes(self, labels):
        """Build dicts of themes/indices from input training labels."""
        all_labels = [c for l in labels for c in l]
        counts = Counter(all_labels)
        print('Distribution of themes: {}\n'.format(counts))
        
        self.themes = {c:n for n,c in enumerate(set(all_labels))}
        self.themesinv = {v:k for k,v in self.themes.items()}
        return self
        
    def _extract_themes(self, probs):
        """Extract theme strings for probabilities that meet self.threshold.

        Argument probs:  List of probabilities

        Returns: Dict of themes and their probabilities
        """
        predicted_themes = {self.themesinv[n]: p for n,p in enumerate(probs)
                            if p >= self.threshold}
        return predicted_themes
