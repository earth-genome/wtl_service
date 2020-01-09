#!/usr/bin/python3

import requests

if __name__ == '__main__':
   resp = requests.get('http://wtl.earthrise.media')
   print('Pinged wtl_service with status code: {}'.format(resp.status_code))
