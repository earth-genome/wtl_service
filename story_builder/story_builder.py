"""Retrieve content, classify, and geolocate entities for a story.

Class StoryBuilder: Parse text and/or image at url, geolocate and cluster
    locations, and classify story.

External function:
    retrieve_content: Parse text and image associate to story.

Usage, with default CLASSSIFIER:
> metadata = {'url': 'http://my.url', etc.}  # only url is required
> builder = StoryBuilder()
> builder(**metadata)

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

#CLASSIFIER = joblib.load('naivebayes/Stacker_models/latest_model.pkl')
PARSE_IMAGES = True  # required True if CLASSIFIER processes image tags
CLASSIFIER = joblib.load(os.path.join(os.path.dirname(__file__),
    '../naivebayes/NBtext_models/latest_model.pkl'))

class StoryBuilder(object):
    """Parse text and/or image at url, geolocate and cluster locations,
        and classify story.

    Attributes:
        classifier: restored instance of (e.g. naivebayes or logistic
            stacking) classifier
        parse_images: True if classifier operates on image tags, else False

    Method:
        __call__: Build a story from url.
    """
    def __init__(self, classifier=CLASSIFIER, parse_images=PARSE_IMAGES):
        self.classifier = classifier
        self.parse_images = parse_images

    def __call__(self, category='/null', **metadata):
        """Build a story.

        Arguments:
            category: database top-level key
            metadata: dict containing at least {'url': 'http://my.url'}

        Returns: a firebaseio.DBItem story, its class label (0/1), and
            a json dump of the story name and record
        """
        try:
            url = metadata['url']
        except KeyError as e:
            raise KeyError('StoryBuilder: Input URL required.')
        record = json.loads(json.dumps(metadata))
        
        try:
            record.update(
                retrieve_content(url, parse_image=self.parse_images))
        except Exception as e:
            raise Exception('Retrieving content for {}\n: {}\n'.format(url,
                repr(e)))
                
        story = firebaseio.DBItem(category, None, record)
        if self.classifier is None:
            return story, None, json.dumps({story.idx: story.record})
        
        classification, probability = self.classifier.classify_story(story)
        story.record.update({'probability': probability})
        if classification == 1:
            print('Accepted for feed @ prob {:.3f}: {}\n'.format(
                    probability, url))
            try:
                ggc = geocluster.GrowGeoCluster(story.record['locations'])
                core_locations = ggc.seed_and_grow()
                story.record.update({'core_locations': core_locations})
            except Exception as e:
                print('Article {}.\n Clustering: {}\n'.format(url, repr(e)))
                story.record.update({'core_locations': {}})
        else:
            print('Declined @ prob {:.2f}: {}\n'.format(probability, url))
        return story, classification, json.dumps({story.idx: story.record})

def retrieve_content(url, parse_image=False):
    """Get parsed text and image from story url.

    Arguments:
        url: url for news story
        parse_image: True/False

    Returns: dict of parsed data types and their data
    """
    try:
        record = extract_text.get_parsed_text(url)
    except:
        raise
    if parse_image:
        try:
            tags = tag_image.get_tags(record['image'])
            record.update({'image_tags': tags})
        except KeyError:
            pass
        except:
            raise
    return record
