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
import numpy as np
from shapely import geometry

from story_builder import geocode
from story_builder import geocluster
from utilities.geobox import geobox

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
        geocoders: list of functions from geocode module
        cluster_tool: instance of GrowGeoCluster class
        classifier: TODO

    External methods: 
        __call__: Geocode, cluster, and score input places.
        assemble_geocodings: Find geo-coordinates with geocoders in sequence.
    """
    def __init__(self, geocoders=[], cluster_tool=None, classifier=None):
        self.geocoders = geocoders if geocoders else [geocode.CageCode()]
        if cluster_tool:
            self.cluster_tool = cluster_tool
        else:
            self.cluster_tool = geocluster.GrowGeoCluster()
        # Temporary ad hoc scoring
        self.classifier = self._score
        #self.classifier = classifier

    def __call__(self, places):
        """Geocode, cluster, and score input places.

        Returns: dict of locations
        """
        candidates = self.assemble_geocodings(places)
        if not candidates:
            raise ValueError('No candidate coordinates found.')
        clusters = self.cluster_tool(candidates)

        for cluster in clusters:
            for name, data in cluster.items():
                data.update({
                    'cluster': list(cluster),
                    'cluster_ratio': len(cluster)/len(candidates),
                    **places[name]
                })
                if self.classifier:
                    data.update({'score': self.classifier(data)})

        locations = {k:v for cluster in clusters for k,v in cluster.items()}

        return locations
        
    def assemble_geocodings(self, places):
        """Find geo-coordinates with (possibly multiple) geocoders.

        Returns: dicts of places with candidate geocodings
        """
        candidates = {}
        for name, data in places.items():
            geolocs = []
            for geocoder in self.geocoders:
                try:
                    geolocs += geocoder(name)
                except Exception as e:
                    print('Geocoding {}: {}'.format(name, repr(e)), flush=True)
            if geolocs:
                candidates.update({name: geolocs})
        return candidates

    # Temporary ad-hoc scoring, to be replaced by a classifier.
    def _score(self, data):
        try:
            sizing = self._size_score(data.get('boundingbox'))
        except TypeError:
            sizing = 0
        clustering = np.sqrt(len(data['cluster']))
        return data['relevance'] * (sizing + clustering)

    def _size_score(self, bounds):
        sides = geobox.get_side_distances(geometry.box(*bounds))
        size = np.mean(sides)
        if size < 2:
            return 3
        elif size < 8:
            return 2
        elif size < 30:
            return 1
        elif size < 100:
            return 0
        else:
            return -.99

