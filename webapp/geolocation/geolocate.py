"""Routines to geocode and score relevance of locations to satellite-based 
reporting. 

The fundamental entity worked on by these routines is a dict, often
taking variable name 'locations' (also sometimes 'places', if not yet
geocoded, or 'cluster'). 

On input, the following keys are required:
'text': string (the place name as it appears in a story)
'relevance': float in [0,1] 
'mentions': list of strings (sentences in which the 'text' appears in a story)

The last can be extracted with the find_mentions function, included in this 
module because the limit parameter impacts classifier architecture.

External class: Geolocate
External function: find_mentions

Usage with defaults and a served classifier: 
> locator = geolocate.Geolocate(model_url='http://52.34.232.26/locations') 
> locator(places)


"""

from collections import OrderedDict
import json

import nltk
import numpy as np
import requests
from shapely import geometry

from geolocation import geocode
from geolocation import geocluster
from utilities.geobox import geobox

MAX_MENTIONS = 6

def find_mentions(place, text, limit=MAX_MENTIONS):
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
        model_url: Url pointing to served model, or None

    External methods: 
        __call__: Geocode, cluster, and score input places.
        assemble_geocodings: Find geo-coordinates with geocoders in sequence.
        classify_relevance: Hit served model to determine relevance of 
            locations.
    """
    def __init__(self, geocoders=[], cluster_tool=None, model_url=None):
        self.geocoders = geocoders if geocoders else [geocode.CageCode()]
        if cluster_tool:
            self.cluster_tool = cluster_tool
        else:
            self.cluster_tool = geocluster.GrowGeoCluster()
        self.model_url = model_url

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

        locations = {k:v for cluster in clusters for k,v in cluster.items()}

        if self.model_url:
            locations = self.classify(locations)

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

    def classify(self, locations):
        """Hit served model to determine relevance of locations."""
        ordered_locs = OrderedDict(locations)
        response = requests.post(
            self.model_url,
            data={'locations_data': json.dumps(list(ordered_locs.values()))})
        try:
            response.raise_for_status()
        except requests.RequestException:
            raise requests.RequestException(response.text)

        for scores, data in zip(response.json(), ordered_locs.values()):
            data.update({'map_relevance': scores})
            
        return dict(ordered_locs)
