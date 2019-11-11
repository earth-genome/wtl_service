"""Uses Watson Natural Language Understanding (NLU) to extract text,
metadata, and higher-order semantic constructs from web-based texts.

Class WatsonReader, descendant of wdc.NaturalLanguageUnderstandingV1:
    External methods:
        get_text: Retrieve text and metadata from url
        get_parsed_text: Retrieve text and select features from url.
        get_sentiment: Retrieve document sentiment.

Minimal usage:
> record = WatsonReader().get_parsed_text(url)

"""

import os

import re
import numpy as np
import watson_developer_cloud as wdc
import watson_developer_cloud.natural_language_understanding_v1 as nlu

from utilities.firebaseio import FB_FORBIDDEN_CHARS

AUTH_ENV_VARS = {
    'username': 'WATSON_USER',
    'password': 'WATSON_PASS'
}

META_TYPES = ['title', 'publication_date', 'image']

# include these entity types:
ENTITY_TYPES = ['Location', 'Facility', 'GeographicFeature']

# but exclude these subtypes:
EXCLUDED_SUBTYPES = ['Continent', 'Country', 'Region']

class WatsonReader(wdc.NaturalLanguageUnderstandingV1):
    """Class to extract text, metadata, and semantic constructs from urls.

    Descendant external methods:
        get_text: Retrieve text and metadata from url
        get_parsed_text: Retrieve text and select features from url.
        get_sentiment: Retrieve document sentiment.

    """
    def __init__(self, version='2018-03-16', username=None, password=None):
        if not username:
            username = os.environ[AUTH_ENV_VARS['username']]
        if not password:
            password = os.environ[AUTH_ENV_VARS['password']]
        super().__init__(version=version, username=username, password=password)
    
    def get_text(self, url):
        """Retrieve text and metadata from url."""
        detailed_response = self.analyze(
            url=url,
            features=nlu.Features(metadata=nlu.MetadataOptions()),
            return_analyzed_text=True)
        x = detailed_response.get_result()

        text = ' '.join(x['analyzed_text'].split())
        metadata = {k:v for k,v in x.get('metadata', {}).items()
                        if k in META_TYPES}
        return text, metadata

    def get_parsed_text(self, url):
        """Retrieve text and select features from url.

        Features are reprocessed before being returned.

        Returns: Dict 
        """
        detailed_response = self.analyze(
            url=url,
            features=nlu.Features(
                metadata=nlu.MetadataOptions(),
                entities=nlu.EntitiesOptions()),
            return_analyzed_text=True)
        x = detailed_response.get_result()

        record = {
            'text': ' '.join(x['analyzed_text'].split()),
            'locations': self._reprocess_entities(x.get('entities', [])),
            **{k:v for k,v in x.get('metadata', {}).items() if k in META_TYPES}
        }
        record.update({'title': self._clean_title(record['title'])})
        return record

    # For an experiment on water-based stories:
    def get_sentiment(self, url):
        """Retrieve document sentiment."""
        detailed_response = self.analyze(
            url=url,
            features=nlu.Features(
                sentiment=nlu.SentimentOptions()),
            return_analyzed_text=False)
        x = detailed_response.get_result()
    
        sentiment = x['sentiment']['document']
        return {sentiment['label']: sentiment['score']}

    # Routines to reprocess Watson output:
    
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
        for symbol in symbols:
            pieces = title.split(symbol)
            lengths = [len(piece) for piece in pieces]
            if max(lengths)/min(lengths) > length_ratio:
                title = pieces[np.argmax(lengths)]
        return title

    # Legacy routine:
    def _clean_keywords(self, keywords):
        """Check forbidden characters and simplify NLU data structure."""
        cleaned = {
            re.sub(FB_FORBIDDEN_CHARS, '', kw['text']): kw['relevance']
            for kw in keywords
        }
        return cleaned
