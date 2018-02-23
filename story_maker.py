"""Create story, text, location items for upload to Firebase.

External functions:

new_story:
    Creates a database entry for the story at given url.
    Returns: A DBItem instance

find_facitilties:
    Find and geolocate features or events in a story.
    Returns: A dict of locations, their coordinates, and relevance

add_facilities:
    Calls find_facilities and adds them directly to a story record

new_text:
    Creates a database entry for the text of a given story
    Returns: A DBItem instance

new_location:
    Creates a database entry for a named facility or geographic feature
    Returns: A DBItem instance
    
"""

import requests
from bs4 import BeautifulSoup
import re

import firebaseio
import facilitize
import geolocate
import extract_text
from extract_text import BAD_REQUESTS, FAUX_HEADERS



def new_story(category='/stories', **metadata):
    """Create a database entry for the story at given url.

    Args:
        category
        metadata to include url (required), and optionally,
         title, date, outlet, description, etc.
    Returns: A DBItem instance
    """    
    url = metadata['url']
    record = {}
    if 'title' not in metadata.keys():
        html = requests.get(url, verify=False)
        if html.status_code in BAD_REQUESTS:
            html = requests.get(url, verify=False, headers=FAUX_HEADERS)
        soup = BeautifulSoup(html.content, 'html.parser')
        try:
            record['title'] = soup.title.string.strip()
        except:
            pass
        try:
            record['date'] = soup.time.attrs['datetime']
        except:
            pass
    record.update(metadata)
    story = firebaseio.DBItem(category,None,record)
    return story

def find_facilities(story, text_chunks=None):
    """Find and geolocate features or events in a story."""
    if text_chunks is None:
        text_chunks = extract_text.get_text(story.record['url'])
    entities = []
    for c in text_chunks:
        entities += facilitize.entity_extraction(c)
    entities = [e for e in entities if facilitize.acceptable_entity(e)]
    locations = {}
    for e in entities:
        coords = geolocate.geocode(e['text'])
        if coords is not None:
            cleaned = {
                'coords': coords,
                'type': e['type'],
                'relevance': e['relevance']
            }
            name = re.sub(firebaseio.FB_FORBIDDEN_CHARS,'',e['text'])
            locations.update({name:cleaned})
    if not locations:
        locations = 'Unlocated'
    return {'locations': locations}

def add_facilities(story, text_chunks=None):
    """Adds facilities directly to a DBItem story.
    """
    if text_chunks == None:
        text_chunks = new_text(story).record
    story.record.update(find_facilities(story, text_chunks))

def new_location(name, record=None, story=None, category='/locations'):
    """Create database item for a location.
    """
    if record is not None:
        try:
            record.pop('relevance')
        except KeyError:
            pass
    else:
        record = {}
        try:
            coords = geolocate.geocode(name)
            record.update({'coords': coords})
        except:
            pass
    if story is not None:
        record.update({'stories': [story.idx]})
    return firebaseio.DBItem(category,name,record)
    
def new_text(story, category='/texts'):
    """Create database item from story text.
    """
    text_chunks = extract_text.get_text(story.record['url'])
    return firebaseio.DBItem(category,story.idx,text_chunks)

def check_sat(text_chunks, chars='satellite'):
    """Check whether the word '(S)satellite' appears in text.
    """
    for c in text_chunks:
        if chars in c.lower():
            return True
    return False

