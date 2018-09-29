"""Reprocess entities and keywords returned from Watson Natural Language
Understanding.

Reprocessing for entities involves (1) filtering unwanted entities;
(2) simplifying entity data returned

Reprocessing for keywords involves simplifying data structure.

For both, dict keys need to be simplified against firebase forbidden
characters ahead of uploading to firebase.

External functions:
    reprocess(entities)
    clean_keywords(keywords)
"""

import os
import re

from utilities.firebaseio import FB_FORBIDDEN_CHARS

# include these entity types:
ENTITY_TYPES = set(['Location', 'Facility', 'GeographicFeature',
                'NaturalEvent'])

# but exclude these subtypes:
EXCLUDED_SUBTYPES = set([
    'Continent',
    'Country',
    'Region',
    'USState',
#    'StateOrCounty',
#    'MountainRange'
])

# And exclude these specific entities.  Add new excluded facilies as a
# separate line (without quotations) to facilities_stop_words.txt.
FACILITIES_SW_FILE = os.path.join(os.path.dirname(__file__),
                            'facilities_stop_words.txt')
with open (FACILITIES_SW_FILE, "r") as swf:
    EXCLUDED_ENTITIES = set([line.strip() for line in swf])

def reprocess(entities):
    entities = filter_entities(entities)
    cleaned = {}
    for e in entities:
        try:
            name = e['disambiguation']['name']
        except KeyError:
            name = e['text']
        name = re.sub(FB_FORBIDDEN_CHARS, '', name)
        try:
            dbpedia = e['disambiguation']['dbpedia_resource']
        except KeyError:
            dbpedia = ''
        try:
            subtype = e['disambiguation']['subtype']
        except KeyError:
            subtype = ''
        data = {
            'relevance': e['relevance'],
            'dbpedia': dbpedia,
            'subtype': subtype
        }
        cleaned.update({name: data})
    return cleaned
    
def filter_entities(entities):
    """Filter entities against custom include/exclude sets."""
    entities = [e for e in entities if e['type'] in ENTITY_TYPES]
    entities = [e for e in entities if not excluded_subtype(e)]
    entities = [e for e in entities if e['text'] not in EXCLUDED_ENTITIES]
    return entities

def excluded_subtype(entity):
    """Check subtypes against excluded set. Returns True if exlcuded."""
    try:
        subtypes = set(entity['disambiguation']['subtype'])
    except KeyError:
        return False
    return bool(subtypes.intersection(EXCLUDED_SUBTYPES))

def clean_keywords(keywords):
    """Check forbidden characters and simplify NLU data structure."""
    cleaned = {
        re.sub(FB_FORBIDDEN_CHARS, '', kw['text']): kw['relevance']
        for kw in keywords
    }
    return cleaned


