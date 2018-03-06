# Routines to determine geographic coordinates relevant to input text

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
        return data['results'][0]['geometry']['location']
    elif data['status'] == 'ZERO_RESULTS':
        return None
    elif data['status'] == 'INVALID_REQUEST':
        return None
    else:
        raise Exception('Geocode error: %s' % data['status'])

    return data
