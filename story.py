"""

External functions:

new_story:
    Creates a database entry for the story at given url.
    Returns: A DBItem instance

find_facitilties:
    Find and geolocate features or events in a story.
    Returns: A dict of locations, their coordinates, and relevance

new_text:
    Creates a database entry for the text of a given story
    Returns: A DBItem instance
    
"""

import urllib2
from bs4 import BeautifulSoup

import firebaseio
import extract_text
import facilitize
import geolocate


def new_story(url, category='/stories', **kwargs):
    """Create a database entry for the story at given url.

    Args:
        url (required)
        category
        kwargs to include, possibly, title, date, outlet, description, and
        and other data to be inscribed in the record
    Return: A DBItem instance
    """
    
    record = {'url':url}
    if 'title' not in kwargs.keys() or 'date' not in kwargs.keys():
        soup = BeautifulSoup(urllib2.urlopen(url), 'html.parser')
    try:
        record['title'] = soup.title.string
    except:
        pass
    try:
        record['date'] = soup.time.attrs['datetime']
    except:
        pass
    record.update(kwargs)
    story = firebaseio.DBItem(category,None,record)
    return story

def find_facilities(story, text_chunks=None):
    """Find and geolocate features or events in a story.
    """
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
                'relevance': e['relevance']
            }
            locations.update({e['text']:cleaned})
    if not locations:
        locations = 'Unlocated'
    return {'locations':locations}

def add_facilities(story, text_chunks=None):
    """Adds facilities directly to a DBItem story.
    """
    story.record.update(find_facilities(story, text_chunks))

def new_location(name, record, story=None, category='/locations'):
    """Create database item for a location.
    """
    #WIP
    record = {coords:location['coords']}
    if story is not None:
        record.update({stories:story.idx})
    return firebaseio.DBItem(category,location,text_chunks)
    
def new_text(story, category='/texts'):
    """Create database item from story text.
    """
    text_chunks = extract_text.get_text(story.record['url'])
    return firebaseio.DBItem(category,story.idx,text_chunks)

def check_sat(text_chunks, word='atellite'):
    """Check whether the word '(S)satellite' appears in text.
    """
    for c in text_chunks:
        if word in c:
            return True
    return False

