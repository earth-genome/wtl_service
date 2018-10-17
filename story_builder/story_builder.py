"""Retrieve content, classify, and geolocate entities for a story.

Class StoryBuilder: Parse text and/or image at url, geolocate and cluster
    locations, and classify story.

Usage, with default CLASSSIFIER:
> metadata = {'date_published': '2018-03-28', ...} #optional records for story
> builder = StoryBuilder()
> builder(url, **metadata)

The CLASSIFIER variable loads a pickled classifier, which has method
classify_story() that operates on an instance of the firebaseio.DBItem class.
It is a BinaryStacker or BinaryBoWClassifier from the bagofwords modules.  

"""


import json
import os

from sklearn.externals import joblib

from story_builder import extract_text
from story_builder import geocluster
from story_builder import tag_image
from utilities import firebaseio


CLASSIFIER = joblib.load(os.path.join(os.path.dirname(__file__),
    '../bagofwords/Stacker_models/latest_model.pkl'))
PARSE_IMAGES = True  # generally set True if CLASSIFIER processes image tags;
    # otherwise the image contribution to classfier will have prob ~50%
    # (cf. current Stacker thresholds ~75%.) 
#THEME_CLASSIFIER = joblib.load(os.path.join(os.path.dirname(__file__),
#    '../themes/MLPtext_models/latest_model.pkl'))
THEME_CLASSIFIER = None

class StoryBuilder(object):
    """Parse text and/or image at url, geolocate and cluster locations,
        and classify story.

    Attributes:
        classifier: restored instance of (e.g. naivebayes or logistic
            stacking) classifier
        parse_images: True for classifier to operate on image tags, else False

    Methods:
        __call__: Build a story from url.
        assemble_content: Assemble parsed url content into a basic story.
        run_classifier: Classify story.
        run_geoclustering: Run geoclustering for story.
    """
    def __init__(self, classifier=CLASSIFIER, parse_images=PARSE_IMAGES,
                 theme_classifier=THEME_CLASSIFIER):
        self.classifier = classifier
        self.parse_images = parse_images
        self.theme_classifier = theme_classifier

    def __call__(self, url, category='/null', **metadata):
        """Build a story from url.

        Arguments:
            url: text string 
            category: database top-level key
            metadata: options parameters to store in story record

        Returns: a firebaseio.DBItem story, its class label (0/1/None), and
            a json dump of the story name and record
        """
        story = self.assemble_content(url, category, **metadata)
        if self.classifier is None:
            classification = None
        else:
            classification, probability = self.run_classifier(story)
            story.record.update({'probability': probability})
            if classification == 1:
                story.record.update({'themes': self.identify_themes(story)})
        story = self.run_geoclustering(story)
        return story, classification, json.dumps({story.idx: story.record})

    def assemble_content(self, url, category='/null', **metadata):
        """Assemble parsed url content into a basic story.

        Arguments:
            url: text string 
            category: database top-level key
            metadata: options parameters to store in story record

        Returns: a firebaseio.DBItem story
        """
        record = json.loads(json.dumps(metadata))
        record.update({'url': url})
        record.update(extract_text.get_parsed_text(url))

        if self.parse_images and record.get('image'):
            record.update({'image_tags': tag_image.get_tags(record['image'])})
            
        return firebaseio.DBItem(category, None, record)

    def run_classifier(self, story):
        """Classify story.

        Argument story:  A firebasio.DBItem story that includes
            parsed content as required for self.classifier (typically,
            returned from assemble_content)

        Returns: a class label (0/1/None) and probability 
        """
        url = story.record['url']
        classification, probability = self.classifier.classify_story(story)
        result = 'Accepted' if classification == 1 else 'Declined'
        print(result + ' for feed @ prob {:.3f}: {}\n'.format(
            probability, url), flush=True)
        
        return classification, probability

    def identify_themes(self, story):
        """Apply the theme classifier to the story.

        Argument story: A DBItem story

        Returns: List of tuples of form (theme, probability)
        """
        try:
            themes = self.theme_classifier.predict_story_themes(story)
        except Exception as e:
            print('Identifying themes for {}\n{}\n'.format(url, repr(e)))
            themes = []
        return themes
        
    def run_geoclustering(self, story):
        """Run geoclustering routines for story.

        Argument story:  A firebasio.DBItem story

        Returns: An updated firebaseio.DBItem story
        """
        if not story.record.get('locations'):
            return story
        
        ggc = geocluster.GrowGeoCluster()
        try:
            core_locations, clusters = ggc(story.record['locations'])
        except Exception as e:
            print('Clustering for {}\n{}\n'.format(story.record['url'],
                                                   repr(e)))
            core_locations, clusters = {}, []
        story.record.update({
            'core_locations': core_locations,
            'clusters': clusters
        })
        return story
