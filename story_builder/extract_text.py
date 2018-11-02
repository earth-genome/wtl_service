"""Uses Watson Natural Language Understanding (NLU) to extract text,
metadata, and higher-order features from input url.

External functions:
    get_text:  Returns text and metadata only from url
    get_parsed_text:  Returns text and features from url

"""

import os

import re
import watson_developer_cloud as wdc
import watson_developer_cloud.natural_language_understanding_v1 as nlu

from config import WATSON_USER, WATSON_PASS
from utilities.firebaseio import FB_FORBIDDEN_CHARS

SERVICE = wdc.NaturalLanguageUnderstandingV1(
        version='2018-03-16',
        username=WATSON_USER,
        password=WATSON_PASS
)

META_TYPES = ['title', 'publication_date', 'image']

# include these entity types:
ENTITY_TYPES = ['Location', 'Facility', 'GeographicFeature']

# but exclude these subtypes:
EXCLUDED_SUBTYPES = ['Continent', 'Region']

def get_text(url):
    """Retrieve text and metadata (only) from url."""
    detailed_response = SERVICE.analyze(
        url=url,
        features=nlu.Features(metadata=nlu.MetadataOptions()),
        return_analyzed_text=True)
    x = detailed_response.get_result()

    text = ' '.join(x['analyzed_text'].split())
    metadata = {k:v for k,v in x.get('metadata', {}).items() if k in META_TYPES}

    return text, metadata

def get_parsed_text(url):
    """Retrieve text and select NLU features from url.

    Features are reprocessed before being returned.

    Returns: Dict 
    """
    detailed_response = SERVICE.analyze(
        url=url,
        features=nlu.Features(
            metadata=nlu.MetadataOptions(),
            entities=nlu.EntitiesOptions()),
        return_analyzed_text=True)
    x = detailed_response.get_result()

    record = {
        'text': ' '.join(x['analyzed_text'].split()),
        'locations': _reprocess_entities(x.get('entities', [])),
        **{k:v for k,v in x.get('metadata', {}).items() if k in META_TYPES}
    }
    return record

# For an experiment on water-based stories:
def get_sentiment(url):
    """Retrieve document sentiment from NLU."""
    detailed_response = SERVICE.analyze(
        url=url,
        features=nlu.Features(
            sentiment=nlu.SentimentOptions()),
        return_analyzed_text=False)
    x = detailed_response.get_result()
    
    sentiment = x['sentiment']['document']
    return {sentiment['label']: sentiment['score']}


# Routines to reprocess Watson output:

def _reprocess_entities(entities):
    """Filter entities and simplify data structure.

    Argument entities: list of Watson dicts
    
    Returns: dict with entity names as keys
    """
    filtered = _filter_entities(entities)
    extracted = dict([_extract_entity(e) for e in filtered])
    return extracted

def _filter_entities(entities):
    """Filter entities against custom include/exclude sets."""
    entities = [e for e in entities if e['type'] in ENTITY_TYPES]
    entities = [e for e in entities if not _check_excluded(e)]
    return entities

def _check_excluded(entity):
    """Check subtypes against excluded set. Returns True if exlcuded."""
    try: 
        subtypes = set(entity['disambiguation']['subtype'])
    except KeyError:
        return False
    return bool(subtypes.intersection(EXCLUDED_SUBTYPES))

def _extract_entity(entity):
    """Extract relevant data from Watson output.

    Argument entity: Watson dict

    Returns: entity name and data
    """
    try:
        name = entity['disambiguation']['name']
    except KeyError:
        name = entity['text']
    
    data = {
        'relevance': entity['relevance'],
        'text': entity['text']
    }
    name = re.sub(FB_FORBIDDEN_CHARS, '', name)
    return name, data

# Legacy routine:
def _clean_keywords(keywords):
    """Check forbidden characters and simplify NLU data structure."""
    cleaned = {
        re.sub(FB_FORBIDDEN_CHARS, '', kw['text']): kw['relevance']
        for kw in keywords
    }
    return cleaned
