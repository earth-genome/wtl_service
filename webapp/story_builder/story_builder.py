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

# Default classifiers
current_dir = os.path.dirname(os.path.abspath(getsourcefile(lambda:0)))
WTL_MODEL = os.path.join(os.path.dirname(current_dir),
                         'bagofwords/Stacker_models/latest_model.pkl')

FLOYD_URL = 'https://www.floydlabs.com/serve/earthrise/projects/themes'

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
    def __init__(self, reader=None, parse_images=False,
                 model=WTL_MODEL, served_models_url=None,
                 refilter=True, geoloc=True, themes=True):
        self.reader = reader if reader else extract_text.WatsonReader()
        self.image_tagger = tag_image.WatsonTagger() if parse_images else None
        self.classifier = joblib.load(model) if model else None
        if refilter and served_models_url:
            self.narrow_band_url = os.path.join(served_models_url, 'narrowband')
        else:
            self.narrow_band_url = None
        if geoloc and served_models_url:
            self.geolocator = geolocate.Geolocate(
                model_url=os.path.join(served_models_url, 'locations'))
        else:
            self.geolocator = None
        self.themes_url = FLOYD_URL if themes else None

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
        self.refilter(story)
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

        Argument story:  A firebasio.DBItem story

        Output: Updates story with a 'probability' if avaiable

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

    def refilter(self, story):
        """Run narrow-band binary classifier(s).

        Output: Updates story with 'narrowband' tags

        Returns: The logical AND of available filter classifications (0/1/None)
        """
        if not self.narrow_band_url:
            return
        clf, labels = self._query(self.narrow_band_url, story.record['text'])
        if clf == 0:
            print('Story {} to be excluded due to {}'.format(
                story.record['url'], labels))
        story.record.update({'narrowband': labels})
        return clf
        
    def run_themes(self, story):
        """Query a served themes classifier.

        Output: Updates story with 'themes' if available
        """
        if not self.themes_url:
            return
        themes = self._query(self.themes_url, story.record['text'])
        story.record.update({'themes': themes})
        return

    def _query(self, url, text):
        """Post text to url."""
        response = requests.post(url, data={'text': text})
        try:
            response.raise_for_status()
        except requests.RequestException:
            raise requests.RequestException(response.text)
        return response.json()
        
    def run_geolocation(self, story):
        """Geolocate places mentioned in story.

        Output: Updates story with 'locations' and possible 'core_location'
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
        
    def _get_core(self, locations):
        """Return a cleaned version of the most relevant location."""
        ranked = []
        for status in ('core', 'relevant'):
            candidates = [d for d in locations.values() if status in
                          d.get('map_relevance', {})]
            # TODO: train to replace ad hoc probability cutoff
            candidates = [c for c in candidates
                          if c['map_relevance'][status] > .5]
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
