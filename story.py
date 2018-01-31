# Routines to generate firebase database entries from stories, locations, text

import firebase
import urllib2
from bs4 import BeautifulSoup
import datetime

import extract_text
import facilitize
import geolocate

FORBIDDEN_CHARS = '.$[]#/'

class DBItem(object):

    def __init__(self, category, idx, record):

        self.category = category
        self.idx = idx
        self.record = record

    def add_facilities(self):
        
        text = extract_text(self.record['url'])
        entities = facilitize.entity_extraction(text)
        entities = [e for e in entities if facilitize.acceptable_entity(e)]
        self.record['locations'] = []
        for e in enumerate(entities):
            cleaned = {
                'text': entity['text'],
                'coords': geolocate.geocode(e),
                'relevance': entity['relevance']
            }
            self.record['locations'].append(cleaned)
        return

    def add_locations(self, **descriptors):
        return



        

        
        
       
def make_idx(record, max_len=64):

    try:
        date = record['date']
    except KeyError:
        date = datetime.datetime.utcnow().isoformat()
        date = date.split('.')[0] + 'Z'
    try:
        title = record['title']
    except KeyError:
        title = ''
    #idx = date.join(str(ord(c)) for c in title)
    idx = date + title # TODO: remove any FORBIDDEN_CHARS
    return idx[:max_len]
    
def story_from_url(url):

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
    return DBItem('/story', idx, record)

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

