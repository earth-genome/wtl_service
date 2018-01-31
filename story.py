# Routines to generate firebase database entries from stories, locations, text

import firebase
import urllib2
from bs4 import BeautifulSoup
import datetime

import extract_text
import facilitize
import geolocate

import pdb

FB_FORBIDDEN_CHARS = '.$[]#/'

class DBItem(object):

    def __init__(self, category, idx, record):

        self.category = category
        self.idx = idx
        self.record = record

    def add_facilities(self):
        
        chunks = extract_text.get_text(self.record['url'])
        entities = []
        for c in chunks:
            entities += facilitize.entity_extraction(c)
        entities = [e for e in entities if facilitize.acceptable_entity(e)]
        self.record['locations'] = {}
        for e in entities:
            coords = geolocate.geocode(e['text'])
            if coords is not None:
                cleaned = {
                    'coords': coords,
                    'relevance': e['relevance']
                }
                self.record['locations'].update({e['text']:cleaned})
        if not self.record['locations']:
            self.record['locations'] = 'Unlocated'
        return

    def add_locations(self, **descriptors):
        return



        

        
        
       
def make_idx(record, max_len=96):

    try:
        pdb.set_trace()
        date = record['date'] # TODO: convert to isoformat if necess.
    except KeyError:
        date = datetime.datetime.utcnow().isoformat()
        date = date.split('.')[0] + 'Z'
    try:
        title = record['title']
    except KeyError:
        title = ''
    #idx = date.join(str(ord(c)) for c in title)
    idx = date + ' ' + title # TODO: remove any FB_FORBIDDEN_CHARS
    return idx[:max_len]
    
def story_from_url(url, category='/stories'):

    soup = BeautifulSoup(urllib2.urlopen(url))
    record = {'url':url}
    try:
        record['title'] = soup.title.string
    except:
        pass
    try:    
        record['date'] = soup.time.attrs['datetime']
    except:
        pass

    idx = make_idx(record)
    return DBItem(category, idx, record)

def story_from_newsapi():
    return
    
def create_text_item(database,story):

    if not known(database,story):
        create_story(XXX)
    try: 
        text = extract_text.get_text(story.record['url'])
        post(database, DBItem('/text', story.idx, text))
    except KeyError:
        pass

# routines to put, delete, query elements of a firebase database:

def post(database,item):

    database.put(item.category,item.idx,item.record)
    return

def delete(database,item):

    database.delete(item.category,item.idx)
    return

def check_known(database,item):
    
    if database.get(item.category,item.idx) is None:
        return False
    else:
        return True

