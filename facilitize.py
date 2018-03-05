"""Reprocess entities returned from Watson Natural Language Understanding.

Reprocessing involves (1) filtering unwanted entities; (2) geolocating;
(3) simplifying data returned to include only relevance and geocoordinates.

"""

import re

from firebaseio import FB_FORBIDDEN_CHARS
import geolocate

import pdb

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
    return entities
    cleaned = {}
    for e in entities:
        name = re.sub(FB_FORBIDDEN_CHARS, '', e['text'])
        coords = geolocate.geocode(e['text'])
        data = {'coords': coords, 'relevance': e['relevance']}
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
    
