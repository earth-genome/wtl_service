"""Reprocess entities and keywords returned from Watson Natural Language
Understanding.

Reprocessing for entities involves (1) filtering unwanted entities;
(2) geolocating; (3) simplifying data returned to include only relevance
and geocoordinates.

Reprocessing for keywords involves simplifying data structure.

For both, dict keys need to be simplified against firebase forbidden
characters ahead of uploading to firebase.

External functions:
    reprocess(entities)
    clean_keywords(keywords)
"""

import re

from firebaseio import FB_FORBIDDEN_CHARS
import geolocate

# include these entity types:
ENTITY_TYPES = set(['Location', 'Facility', 'GeographicFeature',
                'NaturalEvent'])

# but exclude these subtypes:
EXCLUDED_SUBTYPES = set([
    'Continent',
    'Country',
    'Region',
    'USState',
    'StateOrCounty',
    'MountainRange'
])

# And exclude these specific entities.  Add new excluded facilies as a
# separate line (without quotations) to bad_list.txt.
with open ("bad_list.txt", "r") as badfile:
    data = badfile.readlines()
    EXCLUDED_ENTITIES = set([x.strip() for x in data])

def reprocess(entities):
    entities = filter_entities(entities)
    cleaned = {}
    for e in entities:
        try:
            name = e['disambiguation']['name']
            coords = geolocate.geocode(name)
        except KeyError:
            name = e['text']
            coords = geolocate.geocode(name)
        name = re.sub(FB_FORBIDDEN_CHARS, '', name)
        try:
            dbpedia = e['disambiguation']['dbpedia_resource']
        except KeyError:
            dbpedia = None
        data = {
            'coords': coords,
            'relevance': e['relevance'],
            'dbpedia': dbpedia}
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


