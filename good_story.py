# Add to good_locations database a story that is a good candidate to
# have been or that already has been enhanced by satellite imagery.

# usage: python good_story.py 'http://mystory.nytimes.com'

import sys

import config
import story_maker
import firebaseio

def good_story(url):
    """Upload story to firebase database."""
    try:
        story = story_maker.new_story(url=url)
    except Exception as e:
        print('Exception passed: {}'.format(str(e)))
        print('\nFailed to create story from url {}\n'.format(url))
        return
    text = story_maker.new_text(story)
    locations = story_maker.find_facilities(story,text.record)
    story.record.update(locations)
    # TODO: add new locations to database
    location_item = None
    
    # uploads
    gl = firebaseio.DB(config.FIREBASE_GL_URL)
    gl.put_item(story)
    if story_maker.check_sat(text.record):
        gl.put('/satellite_stories',story.idx,story.record)
    gl.put_item(text)
    return

if __name__ == '__main__':
    try:
        url = sys.argv[1]
    except IndexError:
        print('Usage: python good_story.py http://mystory.nytimes.com')
        sys.exit(1)
    good_story(url)




