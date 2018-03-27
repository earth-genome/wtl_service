# Add to good_locations database a story that is a good candidate to
# be enhanced by satellite imagery.

# usage: python good_story.py http://mystory.nytimes.com [-n] [-h]

# Optional flags:
# -h: Help
# -n: This is a negative training case.

import argparse

import config
import firebaseio
from story_builder import story_builder

# logfiles
LOG_NEG = 'sat_neg_cases.txt'
LOG_POS = 'sat_pos_cases.txt'
LOG_SAT = 'sat_stories.txt'

def good_story(url, database, logfile):
    """Build and upload story created from url to firebase database."""
    builder = story_builder.StoryBuilder(classifier=None, parse_images=True)
    try:
        story = builder(category='/stories', url=url)[0]
    except Exception as e:
        print('While creating story: {}'.format(repr(e)))
        print('Failed to create story for url {}\n'.format(url))
        raise
    try:
        database.put_item(story)
        log_url(url, logfile)
        if check_sat(story.record['text']):
            log_url(url, LOG_SAT)
    except Exception as e:
        print('While posting story: {}'.format(repr(e)))
        print('Failed to post story for url {}\n'.format(url))
        raise
    return 

def log_url(url, logfile):
    """Local logging of urls."""
    with open(logfile,'r+') as f:
        lines = [l.strip() for l in f]
        if url not in lines:
            f.write(url+'\n')
    return

def check_sat(text, chars='satellite'):
    """Check whether the word '(S)satellite' appears in text.
    """
    if chars in text.lower():
        return True
    else:
        return False

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
        database = firebaseio.DB(config.FIREBASE_NEG_URL)
        logfile = LOG_NEG
    else:
        database = firebaseio.DB(config.FIREBASE_GL_URL)
        logfile = LOG_POS
        
    story = good_story(args.url, database, logfile)
