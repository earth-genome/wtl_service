"""Routines to determine geographic coordinates relevant to input text.

External class:
    CageCode. Minimal usage: CageCode()(place_name)

External functions:
    google_geocode(text)
    osm_geocode(text)
    dbpedia_geocode(dpbedia_url)
    
Notes: 

As of 2/19/19, only CageCode is deployed in geolocate.py and hence in 
wtl_serice. At some point this code might be cleaned up by deleting the 
other geocoders.

Google geocoding is terse. On a sample of 273 Watson-extracted entity
names, for all but six one or zero geolocations were returned.

OSM geocoding (OpenCage, Nominatim) is verbose, often returning dozens
of responses for incomplete addresses.

Nominatim terms of service require (in BOLD FACE) a maximum of one query 
per second, and the service will (sometimes?) throw a GeocoderTimedOut 
exception if the terms are violated. A query takes around a second on average.
The delay=.5 in osm_geocode should suffice to comply and doesn't affect
the order of magnitude runtime.

"""

import re
import os
import time

import geopy
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from shapely import geometry

from utilities.geobox import geobox

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class CageCode(object):
    """Find lat/lon codings for place names via OpenCage (based on OSM).

    Attributes:
        base_url: OpenCage API url base.
        base_payload: API key and max number of records.

    External method:
        __call__: Geocode input place_name.
    """
    def __init__(self,
                 base_url='https://api.opencagedata.com/geocode/v1/json',
                 N_records=10):
        self.base_url = base_url
        self.base_payload = {
            'key': os.environ['OPENCAGE_API_KEY'],
            'limit': N_records
        }

    def __call__(self, place_name):
        """Geocode place_name. Returns a list of dicts of likely codings."""
        payload = dict({'q': place_name}, **self.base_payload)
        response = requests.get(self.base_url, params=payload)
        response.raise_for_status()
        records = response.json()['results']
        return [self._clean(r) for r in records]

    def _clean(self, record):
        """Format a raw OpenCage record."""
        try: 
            bbox = geobox.viewport_to_shapely_box(record['bounds'])
            bounds = bbox.bounds
        except KeyError:
            bounds = ()

        try:
            osm_url = record['annotations']['OSM']['url']
        except KeyError:
            osm_url = ''
        
        geoloc = {
            'address': record['formatted'],
            'lat': record['geometry']['lat'],
            'lon': record['geometry']['lng'],
            'boundingbox': bounds,
            'osm_url': osm_url
        }
        return geoloc

def google_geocode(text, N_records=1):
    """Find lat/lon coordinates for input text.

    Returns: List of dicts
    """
    base = 'https://maps.googleapis.com/maps/api/place/textsearch/json'
    payload = {
		'query': text,
		'key': os.environ['GOOGLE_GEO_API_KEY']
    }
    data = requests.get(base, params=payload, verify=False).json()

    if data['status'] == 'OK':
        recs = [_clean_google(raw) for raw in data['results'][:N_records]]
        return recs
    elif data['status'] == 'ZERO_RESULTS':
        return []
    elif data['status'] == 'INVALID_REQUEST':
        return []
    else:
        raise Exception('Geocode error: %s' % data['status'])

def _clean_google(raw):
    """Format a raw google record."""
    geom = raw['geometry']
    try: 
        bounds = geobox.viewport_to_shapely_box(geom['viewport']).bounds
    except KeyError:
        bounds = ()
    geoloc = {
        'geocoder': 'google',
        'address': raw.get('formatted_address', ''),
        'lat': geom['location']['lat'],
        'lon': geom['location']['lng'],
        'boundingbox': bounds
    }
    return geoloc

def osm_geocode(place_name, N_records=20, delay=.5):
    """Search osm records for place_name.

    Returns: list of dicts 
    """ 
    nom = geopy.geocoders.Nominatim(user_agent='Earthrise.media')
    time.sleep(delay)
    recs = nom.geocode(place_name, exactly_one=False, addressdetails=False,
                       limit=N_records)
    if recs is None:
        return []
    
    cleaned = [_clean_osm(r.raw) for r in recs]
    return cleaned

def _clean_osm(raw):
    """Format a raw osm record."""
    geoloc = {
        'geocoder': 'osm',
        'address': raw['display_name'],
        'lat': float(raw['lat']),
        'lon': float(raw['lon']),
        'boundingbox': geobox.osm_to_shapely_box(raw['boundingbox']).bounds
    }
    return geoloc

def dbpedia_geocode(url):
    """Extract lat/lon from dbpedia url.

    Arugment url should take the form:
        'http://dbpedia.org/resource/Kathmandu'
    """
    latkey = 'http://www.w3.org/2003/01/geo/wgs84_pos#lat'
    lonkey = 'http://www.w3.org/2003/01/geo/wgs84_pos#long'
    
    jsonbase = 'http://dbpedia.org/data/'
    entity = url.split('resource/')[-1]
    jsonurl = jsonbase + entity + '.json'
    data = requests.get(jsonurl).json()
    try:
        lat = data[url][latkey][0]['value']
        lon = data[url][lonkey][0]['value']
    except KeyError:
        return {}
    geoloc = {
        'source': 'dbpedia',
        'address': re.sub('_', ' ', entity),
        'lat': lat,
        'lon': lon,
    }
    return geoloc


