"""Retrieve content, classify, and geolocate entities for a story.

External class: StoryBuilder

Usage, with default CLASSSIFIER:
> metadata = {'date_published': '2018-03-28', ...} #optional records for story
> builder = StoryBuilder()
> story = builder(url, **metadata)

The CLASSIFIER variable loads a pickled classifier, which has method
classify_story() that operates on an instance of the firebaseio.DBItem class.

"""
import datetime
import json
import os

from sklearn.externals import joblib

from story_builder import extract_text
from story_builder import geolocate
from story_builder import tag_image
from utilities import firebaseio

CLASSIFIER = joblib.load(os.path.join(os.path.dirname(__file__),
    '../bagofwords/Stacker_models/latest_model.pkl'))
PARSE_IMAGES = True  # generally set True if CLASSIFIER processes image tags;
    # otherwise the image contribution to classfier will have prob ~50%
    # (cf. current Stacker thresholds ~75%.) 

class StoryBuilder(object):
    """Parse text and/or image at url, classify story, and geolocate places
        mentioned.

    Attributes:
        classifier: restored instance of (e.g. naivebayes or logistic
            stacking) classifier
        parse_images: True for classifier to operate on image tags, else False
        geolocator: instance of geolocate.Geolocate() class

    Methods:
        __call__: Build a story from url.
        assemble_content: Assemble parsed url content into a basic story.
        run_classifier: Classify story.
        run_geolocation: Geolocate places mentioned in story.
    """
    def __init__(self, classifier=CLASSIFIER, parse_images=PARSE_IMAGES,
                 geolocator=geolocate.Geolocate()):
        self.classifier = classifier
        self.parse_images = parse_images
        self.geolocator = geolocator

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
            if classification == 1:
                story.record.update({'themes': self.identify_themes(story)})
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
                'top_location': _get_top(story.record['locations'])
            })
        except KeyError:
            pass
        return story

def _get_top(locations):
    """Return a cleaned version of the top scored location."""
    try:
        ranked = sorted(locations.items(), key=lambda item:item[1]['score'])
    except KeyError:
        return {}
    name, data = ranked.pop()
    cleaned = {
        'name': name,
        'lat': data['lat'],
        'lon': data['lon'],
        'boundingbox': data['boundingbox'],
        'score': data['score']
    }
    return cleaned
