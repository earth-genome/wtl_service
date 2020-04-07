#!/usr/bin/python3

import requests

if __name__ == '__main__':
   resp = requests.get('http://wtl.earthrise.media/scrape?wires=newsapi&wires=gdelt&max_urls=15000')
   print('Initiated scrape with status code {}:'.format(resp.status_code))
   print(resp.json() if resp.status_code == 200 else resp.text)
