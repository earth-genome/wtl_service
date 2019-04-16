"""Command-line tool to add stories to training and test databases.

Usage: 
> python good_story.py http://mystory.nytimes.com [-n] [-t] [-th THEMES]

For options see the help:
> python good_story.py -h 
"""

import argparse
import json
import os
import sys

from story_builder import story_builder
from utilities import firebaseio

with open('themes/known_themes.txt', 'r') as f:
    KNOWN_THEMES = [l.strip() for l in f.readlines()]

# logfiles
LOG_NEG = 'sat_neg_cases.txt'
LOG_POS = 'sat_pos_cases.txt'
LOG_SAT = 'sat_stories.txt'
LOG_TEST_POS = 'sat_pos_test.txt'
LOG_TEST_NEG = 'sat_neg_test.txt'

def good_story(url, themes, database, db_category, logfile):
    """Build and upload story created from url to firebase database."""
    builder = story_builder.StoryBuilder(classifier=None, parse_images=True)
    try:
        story = builder(url, category=db_category)
    except Exception as e:
        print('While creating story: {}'.format(repr(e)))
        print('Failed to create story for url {}\n'.format(url))
        raise
    story.record.update({'themes': themes})
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
    if not os.path.exists(logfile):
        with open(logfile, 'a') as f:
            f.write(url+'\n')
    else:
        with open(logfile, 'r+') as f:
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
        help='Flag: This is a negative training or test case.'
    )
    parser.add_argument(
        '-t', '--test',
        action='store_true',
        help='Flag: This is a test rather than training story.'
    )
    parser.add_argument(
        '-th', '--themes',
        action='append',
        type=str,
        default=[],
        help='Apply a theme from {}\n'.format(KNOWN_THEMES) +
            '(Option can be used multiple times, or none.)'
    )
        
    args = parser.parse_args()
    if args.negative_case:
        database = firebaseio.DB('negative-training-cases')
        logfile = LOG_TEST_NEG if args.test else LOG_NEG
    else:
        database = firebaseio.DB('good-locations')
        logfile = LOG_TEST_POS if args.test else LOG_POS
    db_category = '/test' if args.test else '/stories'

    if not set(args.themes).issubset(KNOWN_THEMES):
        query = input('Themes {} are not from {}'.format(
            args.themes, KNOWN_THEMES) + '\nContinue? [y/n] ')
        if query.strip().lower() != 'y':
            sys.exit('Exiting...')
    story = good_story(args.url, args.themes, database, db_category, logfile)
