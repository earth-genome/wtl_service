"""Retrieve content, classify, and geolocate entities for a story.

External class: StoryBuilder

Usage, with default MODEL as classifier:
> metadata = {'publication_date': '2018-03-28', ...} # optional 
> builder = StoryBuilder()
> story = builder(url, **metadata)

"""
import datetime
from inspect import getsourcefile
import json
import os

import requests
from sklearn.externals import joblib

from geolocation import geolocate
from story_builder import extract_text
from story_builder import tag_image
from utilities import firebaseio

# Default classifier
current_dir = os.path.dirname(os.path.abspath(getsourcefile(lambda:0)))
MODEL = os.path.join(os.path.dirname(current_dir),
                     'bagofwords/Stacker_models/latest_model.pkl')

FLOYD_URL = 'https://www.floydlabs.com/serve/earthrise/projects/serving'

class StoryBuilder(object):
    """Parse text and/or image at url, classify story, and geolocate places
        mentioned.

    Attributes:
        reader: instance of extract_text.WatsonReader class (required)
        image_tagger: instance of tag_image.WatsonTagger class, or None
        model: path to a pickled (e.g. naivebayes or logistic stacking) 
            classifier, or None
        geolocator: instance of geolocate.Geolocate class, or None

    Methods:
        __call__: Build a story from url.
        assemble_content: Assemble parsed url content into a basic story.
        run_classifier: Classify story.
        run_geolocation: Geolocate places mentioned in story.
    """
    def __init__(self, reader=None, parse_images=False, model=MODEL,
                 geoloc=True, themes=True):
        self.reader = reader if reader else extract_text.WatsonReader()
        self.image_tagger = tag_image.WatsonTagger() if parse_images else None
        self.classifier = joblib.load(model) if model else None
        if geoloc:
            self.geolocator = geolocate.Geolocate(
                model_url=os.path.join(FLOYD_URL, 'locations'))
        else:
            self.geolocator = None
        self.themes_url = os.path.join(FLOYD_URL, 'themes') if themes else None

    def __call__(self, url, category='/null', **metadata):
        """Build a story from url.

        Arguments:
            url: text string 
            category: database top-level key
            metadata: options parameters to store in story record

        Returns: a firebaseio.DBItem story
        """
        story = self.assemble_content(url, category, **metadata)
        self.run_classifier(story)
        self.run_geolocation(story)
        self.run_themes(story)
        return story

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
        record.update({
            'scrape_date': datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        })
        record.update(self.reader.get_parsed_text(url))

        if self.image_tagger and record.get('image'):
            record.update({
                'image_tags': self.image_tagger.get_tags(record['image'])
            })
        return firebaseio.DBItem(category, None, record)

    def run_classifier(self, story):
        """Classify story.

        Argument story:  A firebasio.DBItem story that includes
            parsed content as required for self.classifier (typically,
            returned from assemble_content)

        Output: Updates story.record with a 'probability' if avaiable

        Returns: A class label (0/1/None) 
        """
        if not self.classifier:
            return None
        classification, probability = self.classifier.classify_story(story)
        result = 'Accepted' if classification == 1 else 'Declined'
        print(result + ' for feed @ prob {:.3f}: {}\n'.format(
            probability, story.record['url']), flush=True)
        story.record.update({'probability': probability})
        return classification
        
    def run_geolocation(self, story):
        """Geolocate places mentioned in story.

        Output: Updates story.record with 'locations' and 'core_location'
            if avaiable
        """
        input_places = story.record.get('locations', {})
        if not self.geolocator or not input_places:
            return
        
        for name, data in input_places.items():
            data.update({
                'mentions':
                    geolocate.find_mentions(data['text'], story.record['text'])
            })
        try:
            locations = self.geolocator(input_places)
            story.record.update({'locations': locations})
        except ValueError as e:
            print('Geolocation: {}'.format(repr(e)))
            return 
        except requests.RequestException:
            raise

        story.record.update({
            'core_location': self._get_core(story.record.get('locations', {}))
        })
        return

    def run_themes(self, story):
        """Query an app-based themes classifier.

        Output: Updates story.record with 'themes' if available
        """
        if not self.themes_url:
            return
        
        response = requests.post(self.themes_url,
                                 data={'text': story.record['text']})
        try:
            response.raise_for_status()
        except requests.RequestException:
            raise requests.RequestException(response.json())
        
        story.record.update({'themes': response.json()})
        return
        
    def _get_core(self, locations):
        """Return a cleaned version of the most relevant location."""
        ranked = []
        for status in ('core', 'relevant'):
            candidates = [d for d in locations.values() if status in
                          d.get('map_relevance', {})]
            ranked += sorted(candidates,
                             key=lambda x:x['map_relevance'][status],
                             reverse=True)
        if not ranked:
            return {}
        
        data = next(iter(ranked))
        keys_to_keep = ['boundingbox', 'lat', 'lon', 'mentions', 'osm_url',
                        'map_relevance', 'text']
        return {k:v for k,v in data.items() if k in keys_to_keep}
    
    # Now deprecated, used with ad hoc location scoring:
    def _get_top(self, locations):
        """Return a cleaned version of the top scored location."""
        try:
            ranked = sorted(locations.items(), key=lambda item:item[1]['score'],
                            reverse=True)
            name, data = next(iter(ranked))
        except (KeyError, StopIteration):
            return {}

        keys_to_keep = ['boundingbox', 'lat', 'lon', 'mentions', 'osm_url',
                        'score', 'text']
        cleaned = {k:v for k,v in data.items() if k in keys_to_keep}
        return cleaned
