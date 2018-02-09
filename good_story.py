# Add to good_locations database a story that is a good candidate to
# have been or that already has been enhanced by satellite imagery.

# usage: python good_story.py http://mystory.nytimes.com

import sys

import config
import story_maker
import firebaseio

def good_story(url):
    """Upload story to firebase database."""
    try:
        story = story_maker.new_story(url=url)
    except Exception as e:
        print('Exception passed: {}'.format(repr(e)))
        print('\nFailed to create story from url {}\n'.format(url))
        return
    text = story_maker.new_text(story)
    geolocs = story_maker.find_facilities(story,text.record)
    story.record.update(geolocs)
    # Future: add locations once locations extraction is refined
    """
    if geolocs['locations'] != 'Unlocated':
        locations = [story_maker.new_location(name, record=rec, story=story)
                 for name, rec in geolocs['locations'].iteritems()]
    else:
        locations = []
    """
    
    # uploads
    gl = firebaseio.DB(config.FIREBASE_GL_URL)
    gl.put_item(story)
    if story_maker.check_sat(text.record):
        gl.put('/satellite_stories',story.idx,story.record)
        log_url(url, 'sat_stories.txt')
    else:
        log_url(url, 'sat_candidates.txt')
    gl.put_item(text)

    """
    for l in locations:
        if not gl.check_known(l):
            gl.put_item(l)
        else:
            existing_loc = gl.get('/locations', l.idx)
            # TODO: reconcile l with existing_loc record, in partic
            # adding current story to list of stories
    """
    return

def log_url(url, logfile):
    """Local logging of urls."""
    with open(logfile,'r+') as f:
        lines = [l.strip() for l in f]
        if url not in lines:
            f.write(url+'\n')
    return

if __name__ == '__main__':
    try:
        url = sys.argv[1]
    except IndexError:
        print('Usage: python good_story.py http://mystory.nytimes.com')
        sys.exit(1)
    good_story(url)




