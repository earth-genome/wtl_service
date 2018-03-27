"""Routines to determine geographic coordinates relevant to input text.

Only the first result from the Google API is returned.  Google API seems
relatively terse in its response, as compared to OpenStreetMap.

"""

import sys

sys.path.append('../')
sys.path.append('grab-imagery/')
from nominatim import nominatim
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

from config import GOOGLE_GEO_API_KEY
from geobox import geobox

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def geocode(text):
    """Accepts a text query and returns lat-lon coordinates and a
    bounding box.
    """
    base = 'https://maps.googleapis.com/maps/api/place/textsearch/json'
    payload = {
		'query': text,
		'key': GOOGLE_GEO_API_KEY
    }

    data = requests.get(base, params=payload, verify=False).json()
    if data['status'] == 'OK':
        geoloc = data['results'][0]['geometry']['location']
        # Google uses 'lng' while others (e.g. OSM) use 'lon':
        geoloc = {'lat': geoloc['lat'], 'lon': geoloc['lng']}
        try: 
            viewport = data['results'][0]['geometry']['viewport']
            bbox = geobox.google_to_shapely_box(viewport).bounds
        except KeyError:
            bbox = ()
        return geoloc, bbox
    elif data['status'] == 'ZERO_RESULTS':
        return {}
    elif data['status'] == 'INVALID_REQUEST':
        return {}
    else:
        raise Exception('Geocode error: %s' % data['status'])

    return data

def search_osm(place_name):
    """Search osm records for place_name.

    Returns: list of dicts 
    """
    nom = nominatim.Nominatim()
    recs = nom.query(place_name)
    return recs


