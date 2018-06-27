"""Routines to train, store, and run a bag-of-words classifier for text themes.

Class: ThemeClassifier

This class descends from bagofwords.BoWClassifier, specializing as follows:
-- A default estimator (sklearn MLPClassifier) is proposed in __init__
-- The data_type is fixed to 'text'
-- Training happens only on a single database (defaults to bagofwords.POS_DB)
-- Methods are provided to extract string themes from the output vector
    probabilities provided by BoWClassifier methods

To train with defaults:
tc = ThemeClassifier()
c = train_from_db(freeze_dir='/path/to/save/model')

To get themes for a DBItem story:
themes, probs = c.predict_story_themes(story)


"""

from collections import Counter
from sklearn.multiclass import OneVsRestClassifier 
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import MultiLabelBinarizer

from bagofwords import bagofwords

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
    def __init__(self,
        estimator=OneVsRestClassifier(
            MLPClassifier(
                hidden_layer_sizes=(100,),
                activation='logistic',
                solver='lbfgs',
                warm_start=True,
                verbose=True))):
        super().__init__(estimator, data_type='text')
        
    def predict_text_themes(self, text):
        """Determine theme(s) and their probabilities for a text."""
        probs = self.predict_datum(text)
        return self._extract_themes(probs)

    def predict_story_themes(self, story):
        """Determine theme(s) and their probabilities for a story."""
        probs = self.predict_story(story)
        return self._extract_themes(probs)

    def train_from_dbs(self, db=bagofwords.POS_DB, threshold=THRESHOLD,
                       x_val=None, freeze_dir=None):
        """Train from our Firebase database, with option to freeze model.

        Arguments:
            db: firebaseio.DB instance
            threshold: probabilty threshold 
            x_val: integer k indicating k-fold cross-validation, or None
            freeze_dir: If given, the model will be pickled to this directory
        """
        stories = db.grab_stories()
        texts, labels = [], []
        for s in stories:
            try:
                texts.append(s.record['text'])
            except KeyError:
                continue
            try:
                labels.append(s.record['themes'])
            except KeyError:
                labels.append([])
        all_labels = [c for l in labels for c in l]
        counts = Counter(all_labels)
        print('Distribution of themes: {}\n'.format(counts))
              
        self.themes = {c:n for n,c in enumerate(set(all_labels))}
        self.themesinv = {v:k for k,v in self.themes.items()}
        labelints = [[self.themes[c] for c in l] for l in labels]
        labelbins = MultiLabelBinarizer().fit_transform(labelints)

        self.train(texts, labelbins, threshold=threshold, x_val=x_val)
        if freeze_dir:
            self.freeze(freeze_dir, data=texts, labels=labels, counts=counts)
        return self
        
    def _extract_themes(self, probs):
        """Extract theme strings for probabilities that meet self.threshold.

        Argument probs:  List of probabilities

        Returns: List of tuples of form (theme, prob)
        """
        predicted_themes =  [(self.themesinv[n], p) for n,p in enumerate(probs)
                             if p >= self.threshold]
        return predicted_themes
