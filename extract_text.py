"""Uses Watson Natural Language Understanding (NLU) to extract text,
metadata, and higher-order features from input url.

Features are defined in parse_text(), currently:
    metadata, entities, keywords

External functions:
    get_text:  Returns text and metadata only from url
    get_parsed_text:  Returns text and features from url, with
        entities reprocessed with routines in facilitize.py

"""

import watson_developer_cloud as wdc
import watson_developer_cloud.natural_language_understanding_v1 as nlu

from config import WATSON_USER, WATSON_PASS
import facilitize

AUTH = wdc.NaturalLanguageUnderstandingV1(
        version='2017-02-27',
        username=WATSON_USER,
        password=WATSON_PASS
)

def get_text(url):
    """Retrieve text and metadata (only) from url."""
    x = AUTH.analyze(
        url=url,
        features=nlu.Features(
            metadata=nlu.MetadataOptions() 
        ),
        return_analyzed_text=True
    )

    text = ' '.join(x['analyzed_text'].split())

    return {'text': text, 'metadata': x['metadata']}

def get_parsed_text(url):
    """Retrieve text and select NLU features from url.

    Text and entities are reprocessed before being returned.

    Returns:  dict containing text, metadata, entities, keywords.
    """
    x = AUTH.analyze(
        url=url,
        features=nlu.Features(
            metadata=nlu.MetadataOptions(),
            entities=nlu.EntitiesOptions(), 
			keywords=nlu.KeywordsOptions()
        ),
        return_analyzed_text=True
    )

    parsed = {
        'text': ' '.join(x['analyzed_text'].split()),
        'metadata': x['metadata'],
        'locations': facilitize.reprocess(x['entities']),
        'keywords': x['keywords']
    }
    return parsed

