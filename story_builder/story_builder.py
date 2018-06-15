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

import firebaseio
from story_builder import extract_text
from story_builder import geocluster
from story_builder import tag_image


CLASSIFIER = joblib.load(os.path.join(os.path.dirname(__file__),
    '../bagofwords/Stacker_models/latest_model.pkl'))
PARSE_IMAGES = True  # required True if CLASSIFIER processes image tags

class StoryBuilder(object):
    """Parse text and/or image at url, geolocate and cluster locations,
        and classify story.

    Attributes:
        classifier: restored instance of (e.g. naivebayes or logistic
            stacking) classifier
        parse_images: True if classifier operates on image tags, else False

    Methods:
        __call__: Build a story from url.
        assemble_content: Assemble parsed url content into a basic story.
        run_classifier: Classify story.
        run_geoclustering: Run geoclustering for story.
    """
    def __init__(self, classifier=CLASSIFIER, parse_images=PARSE_IMAGES):
        self.classifier = classifier
        self.parse_images = parse_images

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
        try:
            record.update(extract_text.get_parsed_text(url))
        except Exception as e:
            raise Exception('Retrieving text for {}\n'.format(url)) from e
        if self.parse_images:
            try:
                tags = tag_image.get_tags(record['image'])
                record.update({'image_tags': tags})
            except KeyError:
                pass
            except Exception as e:
                raise Exception('Tagging image for {}\n'.format(url)) from e
        return firebaseio.DBItem(category, None, record)

    def run_classifier(self, story):
        """Classify story.

        Argument story:  A firebasio.DBItem story that includes
            parsed content as required for self.classifier (typically,
            returned from assemble_content)

        Returns: a class label (0/1/None) and probability 
        """
        url = story.record['url']
        try: 
            classification, probability = self.classifier.classify_story(
                story)
        except Exception as e:
            raise Exception('Classifying {}'.format(url)) from e
        result = 'Accepted' if classification == 1 else 'Declined'
        print(result + ' for feed @ prob {:.3f}: {}\n'.format(
            probability, url))
        
        return classification, probability
    
    def run_geoclustering(self, story):
        """Run geoclustering routines for story.

        Argument story:  A firebasio.DBItem story

        Returns: a new firebaseio.DBItem story
        """
        url = story.record['url']
        story = firebaseio.DBItem(story.category,
                                  story.idx,
                                  json.loads(json.dumps(story.record)))

        try:
            ggc = geocluster.GrowGeoCluster()
            core_locations, clusters = ggc(story.record['locations'])
        except Exception as e:
            print('Clustering for article {}\n{}\n'.format(url, repr(e)))
            core_locations, clusters = {}, []
        story.record.update({'core_locations': core_locations})
        story.record.update({'clusters': clusters})
    
        return story
