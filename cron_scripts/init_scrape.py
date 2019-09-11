#!/usr/bin/python3

import requests

if __name__ == '__main__':
   resp = requests.get('http://52.34.232.26/scrape?wires=newsapi&wires=gdelt')
   print('Initiated scrape with status code {}:'.format(resp.status_code))
   print(resp.json() if resp.status_code == 200 else resp.text)