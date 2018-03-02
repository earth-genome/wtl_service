# Add to good_locations database a story that is a good candidate to
# have been or that already has been enhanced by satellite imagery.

# usage: python good_story.py http://mystory.nytimes.com [-n] [-h]

# Optional flags:
# -h: Help
# -n: This is a negative training case.

import argparse
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

def neg_story(url):
    """Upload a negative training case to firebase database."""
    try:
        story = story_maker.new_story(url=url)
    except Exception as e:
        print('Exception passed: {}'.format(repr(e)))
        print('\nFailed to create story from url {}\n'.format(url))
        return
    text = story_maker.new_text(story)
    
    # uploads
    negbase = firebaseio.DB(config.FIREBASE_NEG_URL)
    negbase.put_item(story)
    log_url(url, 'sat_neg_cases.txt')
    negbase.put_item(text)
    return

def log_url(url, logfile):
    """Local logging of urls."""
    with open(logfile,'r+') as f:
        lines = [l.strip() for l in f]
        if url not in lines:
            f.write(url+'\n')
    return

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Add a story to a Firebase story database.'
    )
    parser.add_argument(
        'url',
        type=str,
        help='URL of story to upload.'
    )
    parser.add_argument(
        '-n', '--negative_case',
        action='store_true',
        help=('Flag: This is a negative training case. ' +
            '(True if set, else False.)')
    )
    args = parser.parse_args()
    if args.negative_case:
        neg_story(args.url)
    else:
        good_story(args.url)

