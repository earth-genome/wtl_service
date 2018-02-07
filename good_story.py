# Add to good_locations database a story that is a good candidate to
# have been or that already has been enhanced by satellite imagery.

# usage: python good_story.py 'http://mystory.nytimes.com'

import sys

import config
import story
import firebaseio

def good_story(url):
    """Upload story to firebase database."""
    story_item = story.new_story(url)
    story_item.idx = 'Algae'
    text_item = story.new_text(story_item)
    locations = story.find_facilities(story_item,text_item.record)
    story_item.record.update(locations)
    # TODO: add new locations to database
    location_item = None
    
    # uploads
    gl = firebaseio.DB(config.FIREBASE_GL_URL)
    gl.put_item(story_item)
    if story.check_sat(text_item.record):
        gl.put('/satellite_stories',story_item.idx,story_item.record)
    gl.put_item(text_item)

if __name__ == '__main__':
    try:
        url = sys.argv[1]
    except IndexError:
        print "Usage: python good_story.py http://mystory.nytimes.com"
        sys.exit(1)
    good_story(url)



