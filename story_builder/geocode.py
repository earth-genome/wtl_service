"""Routines to determine geographic coordinates relevant to input text.

External functions:
    google_geocode(text)
    osm_geocode(text)
    dbpedia_geocode(dpbedia_url)
    
Note: 

Google geocoding is terse. On a sample of 273 Watson-extracted entity
names, for all but six one or zero geolocations were returned.

OSM geocoding is verbose, often returning dozens of responses for incomplete
addresses.

"""

import re

import geopy
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from shapely import geometry

from config import GOOGLE_GEO_API_KEY
from utilities.geobox import geobox
from utilities.firebaseio import FB_FORBIDDEN_CHARS

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    
def google_geocode(text, N_records=1):
    """Find lat/lon coordinates for input text.

    Returns: List of dicts
    """
    base = 'https://maps.googleapis.com/maps/api/place/textsearch/json'
    payload = {
		'query': text,
		'key': GOOGLE_GEO_API_KEY
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
        bounds = geobox.google_to_shapely_box(geom['viewport']).bounds
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

def osm_geocode(place_name, N_records=20):
    """Search osm records for place_name.

    Returns: list of dicts 
    """
    nom = geopy.geocoders.Nominatim(user_agent='Earthrise.media')
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

# Deprecated:
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


