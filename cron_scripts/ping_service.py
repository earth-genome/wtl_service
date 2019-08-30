#!/usr/bin/python3

import requests

if __name__ == '__main__':
   resp = requests.get('http://52.34.232.26')
   print('Pinged wtl_service with status code: {}'.format(resp.status_code))
