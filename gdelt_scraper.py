"""Process current stories from GDELT, as hosted at Heroku.

External function:  scrape()

Supporting functions _harvest_urls and _build_and_post are formulated
ad hoc to GDELT.

Usage from main: python gdelt_scraper.py

Outputs:
    All stories and their metadata are uploaded to Firbase (STORY_SEEDS).

    After classification, the best candidate stories are sent to
    WhereToLook ('/WTL') on STORY_SEEDS.  

    Exceptions are logged in EXCEPTION_DIR.
"""

import logging
from logging import handlers
import os
import signal
import sys

import requests

import config
import firebaseio
from story_builder import story_builder

SOURCE_URL = 'https://gdelt-seeds.herokuapp.com/urls'

STORY_SEEDS = firebaseio.DB(config.FIREBASE_URL)

EXCEPTIONS_DIR = 'NewsScraperExceptions'
LOGFILE = 'gdelt.log'

def scrape():

    logger = _build_logger()
    signal.signal(signal.SIGINT, _signal_handler)
    builder = story_builder.StoryBuilder()
    urls = _harvest_urls()

    for url in urls:
        try:
            _build_and_post(url, builder, logger)
        except Exception as e:
            logger.error(url, exc_info=True)

    print('complete')
    return

def _build_and_post(url, builder, logger):
    """Build and post, ad hoc to scraping.

    Arguments:
        url type: str
        builder: story_builder.StoryBuilder instance
        logger: logging.getLogger instance

    Returns: record of post to '/stories' if successful, else {}
    """
    story = builder.assemble_content(url, category='/stories')
    # TODO for GDELT: we should either get titles from GDELT server or
    # check url (where?) before grabbing content
    if STORY_SEEDS.check_known(story):
        return {}
    clf, prob = builder.run_classifier(story)
    story.record.update({'probability': prob})
    if clf == 1:
        story = builder.run_geoclustering(story)
        try: 
            STORY_SEEDS.put('/WTL', story.idx, story.record)            
        except Exception as e:
            logger.error('Uploading to WTL: {}'.format(url), exc_info=True)
        story.record.pop('core_locations')
    story.record.pop('text')
    story.record.pop('keywords')
    return STORY_SEEDS.put('/stories', story.idx, story.record)
        
def _harvest_urls(source_url=SOURCE_URL):
    """Retrieve urls."""
    data = requests.get(source_url)
    urls = data.json()['results']
    return urls

def _build_logger(directory=EXCEPTIONS_DIR, logfile=LOGFILE):
    logger = logging.getLogger(__name__)
    if not os.path.exists(directory):
        os.makedirs(directory)
    trfh = handlers.TimedRotatingFileHandler(
        os.path.join(directory, logfile), when='W6')
    logger.addHandler(trfh)
    return logger

def _signal_handler(*args):
    print('KeyboardInterrupt: Writing logs before exiting...')
    logging.shutdown()
    sys.exit(0)
        
if __name__ == '__main__':
    scrape()
