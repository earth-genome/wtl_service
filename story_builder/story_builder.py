"""Retrieve content, classify, and geolocate entities for a story.

Class StoryBuilder: Parse text and/or image at url, geolocate and cluster
    locations, and classify story.

Usage, with default CLASSSIFIER and flags PARSE_IMAGES, HONE_LOCATIONS:
> metadata = {'date_published': '2018-03-28', ...} #optional records for story
> builder = StoryBuilder()
> builder(url, **metadata)

The CLASSIFIER variable loads a pickled classifier, which has method
classify_story() that operates on an instance of the firebaseio.DBItem class.

"""

import json
import os
import sys

from sklearn.externals import joblib

sys.path.append('../')
import config
import firebaseio
from . import extract_text
from . import geocluster
from . import tag_image

CLASSIFIER = joblib.load(os.path.join(os.path.dirname(__file__),
    '../naivebayes/NBtext_models/latest_model.pkl'))
#CLASSIFIER = joblib.load('naivebayes/Stacker_models/latest_model.pkl')
PARSE_IMAGES = True  # required True if CLASSIFIER processes image tags
HONE_LOCATIONS = True

class StoryBuilder(object):
    """Parse text and/or image at url, geolocate and cluster locations,
        and classify story.

    Attributes:
        classifier: restored instance of (e.g. naivebayes or logistic
            stacking) classifier
        parse_images: True if classifier operates on image tags, else False
        hone_locations: True/False to apply geoclustering routines

    Methods:
        __call__: Build a story from url.
        assemble_content: Assemble parsed url content into a basic story.
        build: Classify and run geoclustering routines for story skeleton.
    """
    def __init__(self,
                 classifier=CLASSIFIER,
                 parse_images=PARSE_IMAGES,
                 hone_locations=HONE_LOCATIONS):
        self.classifier = classifier
        self.parse_images = parse_images
        self.hone_locations = hone_locations

    def __call__(self, url, category='/null', **metadata):
        """Build a story from url.

        Arguments:
            url: text string 
            category: database top-level key
            metadata: options parameters to store in story record

        Returns: a firebaseio.DBItem story, its class label (0/1), and
            a json dump of the story name and record
        """
        skeleton = self.assemble_content(url, category, **metadata)
        story, classification, feed = self.build(skeleton)
        return story, classification, feed

    def assemble_content(self, url, category='/null', **metadata):
        """Assemble parsed url content into a basic story.

        Arguments:
            url: text string 
            category: database top-level key
            metadata: options parameters to store in story record

        Returns: a firebaseio.DBItem story
        """
        record = json.loads(json.dumps(metadata))
        if 'url' not in record.keys():
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

    def build(self, skeleton):
        """Classify and run geoclustering routines for story skeleton.

        Argument skeleton:  A firebasio.DBItem story that includes
            parsed content as required for self.classifier (typically,
            returned from assemble_content)

        Returns: a firebaseio.DBItem story, a class label (0/1/None), and
            a json dump of the story name and record
        """
        url = skeleton.record['url']
        story = firebaseio.DBItem(skeleton.category,
                                  skeleton.idx,
                                  json.loads(json.dumps(skeleton.record)))
        
        if self.classifier is None:
            classification = None
        else:
            try: 
                classification, probability = self.classifier.classify_story(
                    story)
            except Exception as e:
                raise Exception('Classifying {}'.format(url)) from e
            story.record.update({'probability': probability})
            result = 'Accepted' if classification == 1 else 'Declined'
            print(result + ' for feed @ prob {:.3f}: {}\n'.format(
                probability, url))

        if self.hone_locations:
            try:
                ggc = geocluster.GrowGeoCluster(story.record['locations'])
                core_locations = ggc.seed_and_grow()
            except Exception as e:
                print('Clustering for article {}\n{}\n'.format(url, repr(e)))
                core_locations = {}
            story.record.update({'core_locations': core_locations})
                
        return story, classification, json.dumps({story.idx: story.record})
