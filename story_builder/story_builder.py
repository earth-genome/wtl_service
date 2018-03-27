"""Retrieve content, classify, and geolocate entities for a story.

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
PARSE_IMAGES = False  # True if CLASSIFIER processes image tags, else False
CLASSIFIER = joblib.load(os.path.join(os.path.dirname(__file__),
    '../naivebayes/NBtext_models/latest_model.pkl'))

class StoryBuilder(object):

    def __init__(self, classifier=CLASSIFIER, parse_images=PARSE_IMAGES):
        self.classifier = classifier
        self.parse_images = parse_images

    def __call__(self, category='/null', **metadata):
        try:
            url = metadata['url']
        except KeyError:
            raise KeyError('StoryBuilder: Input URL required.')
        record = json.loads(json.dumps(metadata))
        
        try:
            record.update(
                retrieve_content(url, parse_image=self.parse_images))
        except Exception as e:
            raise Exception('Article {}.\n Retrieving content: {}\n'.format(
                url, repr(e)))
                
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
