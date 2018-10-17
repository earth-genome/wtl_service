"""Uses Watson Natural Language Understanding (NLU) to extract text,
metadata, and higher-order features from input url.

Features are defined in parse_text(), currently:
    metadata, entities, keywords

External functions:
    get_text:  Returns text and metadata only from url
    get_parsed_text:  Returns text and features from url, reprocessed
        with routines in facilitize.py

"""

import watson_developer_cloud as wdc
import watson_developer_cloud.natural_language_understanding_v1 as nlu

from config import WATSON_USER, WATSON_PASS
from story_builder import facilitize

SERVICE = wdc.NaturalLanguageUnderstandingV1(
        version='2018-03-16',
        username=WATSON_USER,
        password=WATSON_PASS
)

META_TYPES = ['title', 'publication_date', 'image']

def get_text(url):
    """Retrieve text and metadata (only) from url."""
    detailed_response = SERVICE.analyze(
        url=url,
        features=nlu.Features(metadata=nlu.MetadataOptions()),
        return_analyzed_text=True)
    x = detailed_response.get_result()

    metadata = {k:v for k,v in x['metadata'].items() if k in META_TYPES}
    text = ' '.join(x['analyzed_text'].split())

    return text, metadata

def get_parsed_text(url):
    """Retrieve text and select NLU features from url.

    Text, metadata, and entities are reprocessed before being returned.

    Returns:  dict containing text, metadata, entities, keywords.
    """
    detailed_response = SERVICE.analyze(
        url=url,
        features=nlu.Features(
            metadata=nlu.MetadataOptions(),
            entities=nlu.EntitiesOptions(), 
			keywords=nlu.KeywordsOptions()),
        return_analyzed_text=True)
    x = detailed_response.get_result()

    record = {k:v for k,v in x['metadata'].items() if k in META_TYPES}
    record.update({'text': ' '.join(x['analyzed_text'].split())})
    try:
        locations = facilitize.reprocess(x['entities'])
    except KeyError:
        locations = {}
    try:
        keywords = facilitize.clean_keywords(x['keywords'])
    except KeyError:
        keywords = {}
    record.update({'locations': locations, 'keywords': keywords})
    return record

