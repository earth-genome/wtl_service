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

from sklearn.externals import joblib

from geolocation import geolocate
from story_builder import extract_text
from story_builder import tag_image
from utilities import firebaseio

# Default classifier
current_dir = os.path.dirname(os.path.abspath(getsourcefile(lambda:0)))
MODEL = os.path.join(os.path.dirname(current_dir),
                     'bagofwords/Stacker_models/latest_model.pkl')

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
    def __init__(self, reader=None, parse_images=True, model=MODEL,
                 geoloc=True):
        self.reader = reader if reader else extract_text.WatsonReader()
        self.image_tagger = tag_image.WatsonTagger() if parse_images else None
        self.classifier = joblib.load(model) if model else None
        self.geolocator = geolocate.Geolocate() if geoloc else None

    def __call__(self, url, category='/null', **metadata):
        """Build a story from url.

        Arguments:
            url: text string 
            category: database top-level key
            metadata: options parameters to store in story record

        Returns: a firebaseio.DBItem story
        """
        story = self.assemble_content(url, category, **metadata)
        if self.classifier:
            classification, probability = self.run_classifier(story)
            story.record.update({'probability': probability})
        if self.geolocator:
            story = self.run_geolocation(story)
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

        Returns: a class label (0/1/None) and probability 
        """
        url = story.record['url']
        classification, probability = self.classifier.classify_story(story)
        result = 'Accepted' if classification == 1 else 'Declined'
        print(result + ' for feed @ prob {:.3f}: {}\n'.format(
            probability, url), flush=True)
        
        return classification, probability
        
    def run_geolocation(self, story):
        """Geolocate places mentioned in story.

        Argument story:  A firebasio.DBItem story

        Returns: An updated firebaseio.DBItem story
        """
        input_places = json.loads(json.dumps(story.record['locations']))
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
            story.record.update({'locations': input_places})

        try:
            story.record.update({
                'core_location': self._get_top(story.record['locations'])
            })
        except KeyError:
            pass
        return story

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
