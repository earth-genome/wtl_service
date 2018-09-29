"""Routines to determine geographic coordinates relevant to input text.

External functions:
    google_geocode(text)
    osm_geocode(text)
    dbpedia_geocode(dpbedia_url)
    
If a query returns multiple records, records are filtered (deleted) for
intersection with earlier records in the list.
"""

import re

from geopy import geocoders
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from shapely import geometry

from config import GOOGLE_GEO_API_KEY
from utilities.geobox import geobox
from utilities.firebaseio import FB_FORBIDDEN_CHARS

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    
def google_geocode(text):
    """Accepts a text query and returns lat-lon coordinates and
    (if possible) a bounding box.
    """
    base = 'https://maps.googleapis.com/maps/api/place/textsearch/json'
    payload = {
		'query': text,
		'key': GOOGLE_GEO_API_KEY
    }
    data = requests.get(base, params=payload, verify=False).json()
    
    if data['status'] == 'OK':
        cleaned = []
        for d in data['results']:
            try:
                address = ', '.join((d['name'], d['formatted_address']))
            except KeyError:
                address = d['name']
            geom = d['geometry']
            try: 
                bounds = geobox.google_to_shapely_box(geom['viewport']).bounds
            except KeyError:
                bounds = ()
            if _check_intersects(bounds, cleaned):
                continue
            # Google uses 'lng' while others (e.g. OSM) use 'lon':
            geoloc = {
                'source': 'google',
                'address': _clean_address(address),
                'types': d['types'],
                'lat': geom['location']['lat'],
                'lon': geom['location']['lng'],
                'boundingbox': bounds
            }
            cleaned.append(geoloc)
        return cleaned
    elif data['status'] == 'ZERO_RESULTS':
        return []
    elif data['status'] == 'INVALID_REQUEST':
        return []
    else:
        raise Exception('Geocode error: %s' % data['status'])
    return


def osm_geocode(place_name):
    """Search osm records for place_name.

    Returns: list of dicts 
    """
    nom = geocoders.Nominatim(user_agent='Earthrise.media')
    recs = nom.geocode(place_name,
                       exactly_one=False,
                       addressdetails=False,
                       limit=20)
    if recs is None:
        return []
    else:
        recs = [r.raw for r in recs]
    cleaned = []
    for r in recs:
        bounds = geobox.osm_to_shapely_box(r['boundingbox']).bounds
        if _check_intersects(bounds, cleaned):
            continue
        geoloc = {
            'source': 'osm',
            'address': _clean_address(r['display_name']),
            'types': [r['type']],
            'lat': float(r['lat']),
            'lon': float(r['lon']),
            'boundingbox': bounds
        }
        cleaned.append(geoloc)
    return cleaned


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
        'address': _clean_address(re.sub('_', ' ', entity)),
        'lat': lat,
        'lon': lon,
    }
    return geoloc

def _check_intersects(bounds, geolocs):
    """Check if coordinate bounds intersect any bounding boxes in geolocs.

    Arguments:
        bounds: list or tuple of coordinates
        geolocs: list of dicts with 'boundingbox' as key
        
    Returns: True/False
    """
    bbox = geometry.box(*bounds)
    query_boxes = []
    for g in geolocs:
        try:
            query_boxes.append(geometry.box(*g['boundingbox']))
        except KeyError:
            query_boxes.append(geometry.Point(g['lon'], g['lat']))
    for qb in query_boxes:
        if bbox.intersects(qb):
            return True
    return False

def _clean_address(address):
    return re.sub(FB_FORBIDDEN_CHARS, '', address)
