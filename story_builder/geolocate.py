"""Routines to geocode and score relevance of locations to satellite-based 
reporting. 

The fundamental entity worked on by these routines is a dict, often
taking variable name 'locations' (also sometimes 'places', if not yet
geocoded, or 'cluster') of the following form(s):

# TODO: update these examples:

Initially as input:
places = 
{'Maputo': {'dbpedia': 'http://dbpedia.org/resource/Maputo',
  'relevance': 0.846839,
  'subtype': ['AdministrativeDivision', 'City']},
 'Mozambique': {'dbpedia': '',
  'relevance': 0.484892,
  'subtype': ['StateOrCounty']}}

Final output:
core_locations =
{'Maputo, Mozambique': {'address': 'Maputo, Mozambique',
   'boundingbox': (32.5233079, -25.9839715, 32.6980592, -25.8085457),
   'dbpedia': 'http://dbpedia.org/resource/Maputo',
   'lat': -25.969248,
   'lon': 32.5731746,
   'name': 'Maputo',
   'relevance': 0.846839,
   'source': 'google',
   'subtype': ['AdministrativeDivision', 'City'],
   'types': ['locality', 'political']}}
   
The 'relevance', 'text', and 'mentions' keys are required. 'Mentions' can be
extracted with the find_mentions function, included in this module because
the limit parameter impacts classifier architecture.

External class: Geolocate
External function: find_mentions

# TODO: add usage
Usage from 

"""

import functools

import nltk

from story_builder import geocode
from story_builder import geocluster

def find_mentions(place, text, limit=6):
    """Extract sentences where place is mentioned in text.
    
    Arguments:
        place: string to find in sentences of text
        text: long string to be split into sentences

    Returns: list of sentences
    """
    sentences = nltk.sent_tokenize(text)
    mentions = [s for s in sentences if place in s]
    return mentions[:limit]

class Geolocate(object):
    """Class to geolocate and score locations.

    Attributes:
        terse_geocoder, verbose_geocoder: functions from geocode module
        cluster_tool: instance of GrowGeoCluster class
        classifier: TODO

    External methods: 
        __call__: Geocode, cluster, and score input places.
        iterative_geocode: Find geo-coordinates with terse and verbose 
            geocoders in sequence.
        find_mentions: Find setences where place is mentioned in a text.
            
    """
    def __init__(self, 
                 terse_geocoder=functools.partial(
                     geocode.google_geocode, N_records=1),
                 verbose_geocoder=functools.partial(
                     geocode.osm_geocode, N_records=20),
                 cluster_tool=geocluster.GrowGeoCluster(),
                 classifier=None):
        self.terse_geocoder = terse_geocoder
        self.verbose_geocoder = verbose_geocoder
        self.cluster_tool = cluster_tool
        self.classifier = classifier

    def __call__(self, places):
        """Geocode, cluster, and score input places."""
        locations, candidated = self.iterative_geocode(places)
        
        seeds = self.cluster_tool.seed(locations)
        grown = self.cluster_tool.grow(seeds, candidated)

        good_locations = {}
        for cluster in grown:
            for name, data in cluster.items():
                data.update({'cluster': list(cluster.keys())})
                # TODO: add classifier
                data.update({'score': None})
                good_locations.update({name: data})

        return good_locations
        
    def iterative_geocode(self, places):
        """Find geo-coordinates with terse and verbose geocoders in sequence.

        Returns: dicts of places uniquely located and those with multiple 
            candidates
       """
        locations, _, unlocated = self._bulk_geocode(
            places, geocoder=self.terse_geocoder)
        new_locations, candidated, _ = self._bulk_geocode(
            unlocated, geocoder=self.verbose_geocoder)
        locations.update(**new_locations)
        return locations, candidated

    def _bulk_geocode(self, places, geocoder):
        """Find geo-coordinates for input places."""
        located, candidated, unlocated = {}, {}, {}
        for name, data in places.items():
            try: 
                geolocs = geocoder(name)
            except Exception as e:
                print('Geocoding {}: {}'.format(name, repr(e)), flush=True)
                geolocs = []
            if len(geolocs) == 0:
                unlocated.update({name: data})
            elif len(geolocs) == 1:
                located.update({name: dict(geolocs[0], **data)})
            else:
                candidated.update({name: dict({'candidates': geolocs}, **data)})

        return located, candidated, unlocated
