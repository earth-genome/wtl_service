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
                 N_records=40):
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
            bbox = _viewport_to_shapely_box(record['bounds'])
            bounds = bbox.bounds
        except KeyError:
            bounds = ()

        try:
            osm_url = record['annotations']['OSM']['url']
        except KeyError:
            osm_url = ''

        geoloc = {
            'address': self._format_address(record),
            'lat': record['geometry']['lat'],
            'lon': record['geometry']['lng'],
            'boundingbox': bounds,
            'osm_url': osm_url,
            'components': record['components']
        }

        return geoloc

    def _format_address(self, record):
        """Format address from raw OpenCage record."""

        whitelist = ['village', 'hamlet', 'town', 'locality', 'suburb',
                     'city', 'county', 'state_code', 'state']

        formatted = record['formatted']
        components = record['components']
        
        location = []
        for k in whitelist:
            value = components.get(k, 'Null Component')
            if value in formatted and value not in location:
                location.append(value)

        if components.get('country'):
            location.append(components['country'])

        if len(location) > 3:
            location = location[:1] + location[-2:]
        
        reformatted = ', '.join(location)

        return reformatted if reformatted else formatted
    
class BingCode(object):
    
    def __init__(self,
                 base_url='http://dev.virtualearth.net/REST/v1/Locations?',
                 N_records=20):
        self.base_url = base_url
        self.base_payload = {
            'key': os.environ['BINGMAPS_API_KEY'],
            'maxResults': N_records
        }

    def __call__(self, place_name):
        """Geocode place_name. Returns a list of dicts of likely codings."""
        payload = dict({'query': place_name}, **self.base_payload)
        results = requests.get(self.base_url, params=payload).json()
        return [self._clean(r)
                for s in results.get('resourceSets', [])
                for r in s.get('resources', [])]

    def _clean(self, record):
        """Creates results in OSM format from Bing Maps data"""
        
        lat, lon = record.get('point', {}).get('coordinates', [None, None])
        
        geoloc = {
            'address': self._format_address(record),    
            'lat': lat,
            'lon': lon,
            'boundingbox': self._format_bbox(record.get('bbox')),
            'components': record.get('address')
        }
            
        return geoloc

    def _format_address(self, record,
                        whitelist=['locality','adminDistrict2',
                                   'adminDistrict', 'countryRegion']):
        """Reformats address to include country"""

        components = record.get('address', {})
        
        address = [components.get(w) for w in whitelist if components.get(w)]
        
        if len(address) > 3:
            address = address[:1] + address[-2:]
            
        address = ', '.join(address)
        
        return address if address else components['formattedAddress']
        
    def _format_bbox(self, bounding_box):
        """Converts bbox to OSM format for consistency with code base"""

        if bounding_box:

            lat = bounding_box[0], bounding_box[2]
            lon = bounding_box[1], bounding_box[3]

            return min(lon), min(lat), max(lon), max(lat)
        
        else:
            
            return []

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
        bounds = _viewport_to_shapely_box(geom['viewport']).bounds
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
        'boundingbox': _osm_to_shapely_box(raw['boundingbox']).bounds
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

# Bounding box conversions

def _viewport_to_shapely_box(viewport):
    """Convert a Google or OpenCage viewport to a shapely box.

    Argument viewport: A viewport is a dict of form:
        {'northeast': {'lat': -33.9806474, 'lng': 150.0169685},
          'southwest': {'lat': -39.18316069999999, 'lng': 140.9616819}}

    Returns: shapely box
    """
    points = geometry.asMultiPoint([[p['lng'], p['lat']]
                                    for p in viewport.values()])
    return geometry.box(*points.bounds)

def _osm_to_shapely_box(osm_bbox):
    """Convert a bounding box in OSM convention to a shapely box.

    OSM retuns strings in order (S Lat, N Lat, W Lon, E Lon),
        while a shapely box takes arguments:
        shapely.geometry.box(minx, miny, maxx, maxy, ccw=True)

    Arugment osm_bbox: boundingbox from an OSM record

    Returns: shapely box
    """
    bounds = np.array(osm_bbox, dtype=float)
    return geometry.box(*bounds[[2,0,3,1]])
