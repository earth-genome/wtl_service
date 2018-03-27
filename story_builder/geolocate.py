# Routines to determine geographic coordinates relevant to input text

import sys

sys.path.append('../')
#from geopy.geocoders import Nominatim
from nominatim import nominatim
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

from config import GOOGLE_GEO_API_KEY

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def geocode(text):
	# Accepts a text query and returns the lat-long coordinates.  Only the
	# first result is returned, if multiple are found.

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
        return geoloc
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

# alternate using geopy often times out:
"""
def search_osm(place_name):

    nom = Nominatim()
    recs = nom.geocode(place_name,
                       exactly_one=False,
                       addressdetails=True,
                       geometry='geojson')
    return recs.raw
"""
