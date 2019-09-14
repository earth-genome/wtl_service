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
from watson_developer_cloud import WatsonApiException

from geolocation import geolocate
from story_builder import extract_text
from story_builder import tag_image
from utilities import firebaseio
from utilities import log_utilities

# Default classifiers
current_dir = os.path.dirname(os.path.abspath(getsourcefile(lambda:0)))
WTL_MODEL = os.path.join(os.path.dirname(current_dir),
                         'bagofwords/Stacker_models/latest_model.pkl')

served_models_url = 'http://wtl.earthrise.media'
NARROWBAND_URL = os.path.join(served_models_url, 'narrowband')
THEMES_URL = os.path.join(served_models_url, 'themes')
GEOLOC_URL = os.path.join(served_models_url, 'locations')

WEATHER_CUT = .25

class StoryBuilder(object):
    """Parse text and/or image at url, classify story, and geolocate places
        mentioned.

    Attributes:
        reader: instance of extract_text.WatsonReader class (required)
        image_tagger: instance of tag_image.WatsonTagger class, or None
        reject_for_class: bool to abort build on negative classification 
            from any binary model
        main_model: restored bagofwords classifier or None
        narrowband_url: url for additional served binary classifier, or None
        themes_url: url for served themes classifier, or None
        weather_cut: probability cutoff for rejecting stories by weather signal
        geolocator: instance of geolocate.Geolocate class, or None
        logger: python logging instance

    Methods:
        __call__: Build a story from url.
        assemble_content: Assemble parsed url content into a basic story.
        classify: Apply main model to story.
        refilter: Run served narrow-band binary classifier.
        apply_themes: Query a served themes classifier.
        run_geolocation: Geolocate places mentioned in story.
    """
    def __init__(self,
                 reader=None,
                 parse_images=False,
                 reject_for_class=True,
                 main_model=WTL_MODEL,
                 narrowband_url=NARROWBAND_URL,
                 themes_url=THEMES_URL,
                 weather_cut = WEATHER_CUT,
                 geoloc_url=GEOLOC_URL,
                 logger=None):
        self.reader = reader if reader else extract_text.WatsonReader()
        self.image_tagger = tag_image.WatsonTagger() if parse_images else None
        self.reject_for_class = reject_for_class
        
        self.main_model = joblib.load(main_model) if main_model else None
        self.narrowband_url = narrowband_url
        self.themes_url = themes_url
        self.weather_cut = weather_cut
        if geoloc_url:
            self.geolocator = geolocate.Geolocate(model_url=geoloc_url)
        else:
            self.geolocator = None
            
        if logger:
            self.logger = logger
        else:
            self.logger = log_utilities.build_logger(
                handler=log_utilities.get_stream_handler())

    def __call__(self, url, category='/null', **metadata):
        """Build a story from url.

        Arguments:
            url: text string 
            category: database top-level key
            metadata: options parameters to store in story record

        Returns: a firebaseio.DBItem story on success, or None
        """
        try:
            story = self.assemble_content(url, category=category, **metadata)
        except WatsonApiException as e:
            self.logger.warning('Assembling content: {}:\n{}'.format(e, url))
            return

        clf = self.classify(story)
        if self._abort(clf):
            return
        
        try: 
            clf = self.refilter(story)
            if self._abort(clf):
                return
        except requests.RequestException as e:
            self.logger.warning('Narrowband: {}:\n{}'.format(e, url))

        try:
            self.apply_themes(story)
            if self._abort_for_weather(story):
                return
        except requests.RequestException as e:
            self.logger.warning('Themes: {}:\n{}'.format(e, url))
            
        try: 
            self.run_geolocation(story)
        except requests.RequestException as e:
            self.logger.warning('Geolocation: {}:\n{}'.format(e, url))

        return story

    def _abort(self, clf):
        """Determine whether or not to abort build on a story.

        Argument clf: int (0/1) or NoneType
        
        Returns: bool
        """
        if not self.reject_for_class:
            return False
        return True if clf == 0 else False

    def _abort_for_weather(self, story):
        """Determine whether to abort build based on weather signal.

        Output: Pops weather from story themes.

        Returns: bool
        """
        weather_prob = story.record.get('themes', {}).pop('weather', {})
        return True if weather_prob > self.weather_cut else False

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

    def classify(self, story):
        """Apply main model to story.

        Argument story:  A firebasio.DBItem story

        Output: Updates story with a 'probability' if avaiable

        Returns: A class label (0/1/None) 
        """
        if not self.main_model:
            return
        clf, probability = self.main_model.classify_story(story)
        result = 'Accepted' if clf == 1 else 'Declined'
        print(result + ' for feed @ prob {:.3f}: {}\n'.format(
            probability, story.record['url']), flush=True)
        story.record.update({'probability': probability})
        return clf

    def refilter(self, story):
        """Run served narrow-band binary classifier.

        Output: Updates story with 'narrowband' labels

        Returns: A class label (0/1/None)
        """
        if not self.narrowband_url:
            return
        clf, labels = self._query(self.narrowband_url, story.record['text'])
        if clf == 0:
            print('Story {} to be excluded due to {}'.format(
                story.record['url'], labels), flush=True)
        story.record.update({'narrowband': labels})
        return clf
        
    def apply_themes(self, story):
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

