"""Applications of IBM Watson ML to parse text and images.

Class Reader, descendant of ibm_watson.NaturalLanguageUnderstandingV1:
    External methods:
        get_text: Retrieve text and metadata from url
        get_parsed_text: Retrieve text and select features from url.
        get_sentiment: Retrieve document sentiment.

Usage:
> record = Reader().get_parsed_text(url)

Class Tagger, descendant of ibm_watson.VisualRecognitionV3
    External method: get_tags

Usage: 
> tags = Tagger().get_tags(img_url)

Class PreReader: 
    External method: get_text: Retrieve text from url.
Included because Watson is expensive. Uses the open-source boilerplate package.

"""

import os
import re

import boilerpipe.extract
import ibm_cloud_sdk_core
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
import ibm_watson
import ibm_watson.natural_language_understanding_v1 as nlu
import numpy as np

from firebaseio import FB_FORBIDDEN_CHARS

AUTH_ENV_VARS = {
    'language_api_key': 'WATSON_LANGUAGE_API_KEY',
    'language_service_url': 'WATSON_LANGUAGE_SERVICE_URL',
    'vision_api_key': 'WATSON_VISION_API_KEY'
}

META_TYPES = ['title', 'publication_date', 'image']

# include these entity types:
ENTITY_TYPES = ['Location', 'Facility', 'GeographicFeature']

# but exclude these subtypes:
EXCLUDED_SUBTYPES = ['Continent', 'Country', 'Region']

# For visual recogntion:
EXCLUDED_TAG_WORDS = ['color']

WATSON_EXCEPTIONS = (ibm_watson.ApiException,
                     ibm_cloud_sdk_core.api_exception.ApiException)

class PreReader(object):
    """Class for simple open-source text extraction."""
    def __init__(self, extractor='ArticleSentencesExtractor'): 
        self.extractor = extractor 
        
    def get_text(self, url):
        """Retrieve text from url."""
        ex = boilerpipe.extract.Extractor(extractor=self.extractor, url=url)  
        record = {'text': ' '.join(ex.getText().split())}
        return record
    
class Reader(ibm_watson.NaturalLanguageUnderstandingV1):
    """Class to extract text, metadata, and semantic constructs from urls.

    Descendant external methods:
        get_text: Retrieve text and metadata from url
        get_parsed_text: Retrieve text and select features from url.
        get_sentiment: Retrieve document sentiment.

    """
    def __init__(self, version='2018-03-16', apikey=None, service_url=None):
        if not apikey:
            apikey = os.environ[AUTH_ENV_VARS['language_api_key']]
        super().__init__(
            version=version, authenticator=IAMAuthenticator(apikey))
        if not service_url:
            service_url = os.environ[AUTH_ENV_VARS['language_service_url']]
        self.set_service_url(service_url)
    
    def get_text(self, url):
        """Retrieve text and metadata from url."""
        detailed_response = self.analyze(
            url=url,
            features=nlu.Features(metadata={}),
            return_analyzed_text=True)
        x = detailed_response.get_result()

        record = {
            'text': ' '.join(x['analyzed_text'].split()),
            **{k:v for k,v in x.get('metadata', {}).items() if k in META_TYPES}
        }
        record.update({'title': self._clean_title(record.get('title'))})
        return record

    def get_parsed_text(self, url):
        """Retrieve text and select features from url."""
        detailed_response = self.analyze(
            url=url,
            features=nlu.Features(metadata={}, entities=nlu.EntitiesOptions()),
            return_analyzed_text=True)
        x = detailed_response.get_result()

        record = {
            'text': ' '.join(x['analyzed_text'].split()),
            'locations': self._reprocess_entities(x.get('entities', [])),
            **{k:v for k,v in x.get('metadata', {}).items() if k in META_TYPES}
        }
        record.update({'title': self._clean_title(record.get('title'))})
        return record

    def get_entities(self, url):
        """Retrieve entities from document."""
        detailed_response = self.analyze(
            url=url,
            features=nlu.Features(entities=nlu.EntitiesOptions()),
            return_analyzed_text=False)
        x = detailed_response.get_result()

        entities = self._reprocess_entities(x.get('entities', []))
        return entities

    # For an experiment on water-based stories:
    def get_sentiment(self, url):
        """Retrieve document sentiment."""
        detailed_response = self.analyze(
            url=url,
            features=nlu.Features(sentiment=nlu.SentimentOptions()),
            return_analyzed_text=False)
        x = detailed_response.get_result()
    
        sentiment = x['sentiment']['document']
        return {sentiment['label']: sentiment['score']}

    def _reprocess_entities(self, entities):
        """Filter entities and simplify data structure.

        Argument entities: list of Watson dicts
    
        Returns: dict with entity names as keys
        """
        filtered = self._filter_entities(entities)
        extracted = dict([self._extract_entity(e) for e in filtered])
        return extracted

    def _filter_entities(self, entities):
        """Filter entities against custom include/exclude sets."""
        entities = [e for e in entities if e['type'] in ENTITY_TYPES]
        entities = [e for e in entities if not self._check_excluded(e)]
        return entities

    def _check_excluded(self, entity):
        """Check subtypes against excluded set. Returns True if exlcuded."""
        try: 
            subtypes = set(entity['disambiguation']['subtype'])
        except KeyError:
            return False
        return bool(subtypes.intersection(EXCLUDED_SUBTYPES))

    def _extract_entity(self, entity):
        """Extract relevant data from Watson output.

        Argument entity: Watson dict

        Returns: entity name and data
        """
        data = {
            'relevance': entity['relevance'],
            'text': entity['text']
        }
        name = re.sub(FB_FORBIDDEN_CHARS, '', entity['text'])
        return name, data

    def _clean_title(self, title, symbols = [' | ', ' – ', ' - '],
                     length_ratio = 1.5):
        """Remove extraneous material in an article title.

        Arguments:
            title: News article title 
            symbols: List of patterns on which to iteratively split title
            length_ratio: Relative length factor: When the longest segment of
                the split title is longer than the shortest by at least this 
                factor, the longest is captured as the cleaned title. The
                operating heuristic is that phrases extraneous to the intended
                title (e.g. an outlet name) tend to be short.
        """
        if not title:
            return ''
        for symbol in symbols:
            pieces = title.split(symbol)
            lengths = [len(piece) for piece in pieces]
            if max(lengths)/min(lengths) > length_ratio:
                title = pieces[np.argmax(lengths)]
        return title

# Note: IBM has cancelled their VisualRecognition service and this
# no longer functions.

# class Tagger(ibm_watson.VisualRecognitionV3):
class Tagger():
    """Class to identify objects, qualities, and themes in images.

    Descendant external method:
        get_tags: Apply Watson Vision Recognition to label an image.

    """
    def __init__(self, version='2018-03-19', apikey=None):
        
        memo = 'IBM Visual Recognition service has been cancelled.'
        raise NotImplementedError(memo)
    
        if not apikey:
            apikey = os.environ[AUTH_ENV_VARS['vision_api_key']]
        super().__init__(
            version=version, authenticator=IAMAuthenticator(apikey))
    
    def get_tags(self, img_url):
        """Apply Watson Vision Recognition to label content of image.
    
        Returns:  Dict of class names and relevance scores.
        """
        try:
            result = self.classify(url=img_url).get_result()
            classlist = result['images'][0]['classifiers'][0]['classes']
        except (*WATSON_EXCEPTIONS, IndexError, KeyError) as e:
            print('Tagging image: {}'.format(repr(e)))
            classlist = []
        
        return self._clean_tags(classlist)

    def _clean_tags(self, classlist):
        """Clean classlist to various specs.

        The function removes Firebase forbidden characters, simplifies the
            data structure, and filters against EXCLUDED_TAG_WORDS.

        Argument classlist: list of dicts with keys 'class' and 'score'

        Returns: dict
        """
        tags = {
            re.sub(FB_FORBIDDEN_CHARS, '', c['class']):c['score']
            for c in classlist
        }
        for excl in EXCLUDED_TAG_WORDS:
            tags = {k:v for k,v in tags.items() if excl not in k}
        return tags
