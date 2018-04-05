"""Process current stories from a news wire.

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

import datetime
import logging
from logging import handlers
import os
import random
import signal
import sys

import requests

import config
import firebaseio
from story_builder import story_builder

WIRE_URLS = {
    'newsapi': 'https://newsapi.org/v2/everything',
    'gdelt': 'https://gdelt-seeds.herokuapp.com/urls'
}

# NewsAPI:
OUTLETS_FILE = 'newsapi_outlets.txt'
#FROM_DATE = datetime.date.today() - datetime.timedelta(days=2)
FROM_DATE = datetime.date.today()

STORY_SEEDS = firebaseio.DB(config.FIREBASE_URL)

EXCEPTIONS_DIR = 'NewsScraperExceptions_logs'
LOGFILE = 'newswire.log'

def scrape(wires):

    logger = _build_logger()
    signal.signal(signal.SIGINT, _signal_handler)
    builder = story_builder.StoryBuilder()
    records = _harvest_records(wires)

    for rec in records:
        if 'title' in rec.keys():
            provis_story = firebaseio.DBItem('/stories', None, rec)
            if STORY_SEEDS.check_known(provis_story):
                continue
        url = rec.pop('url')
        try:
            _build_and_post(url, builder, logger, **rec)
        except Exception as e:
            logger.error(url, exc_info=True)

    print('complete')
    return

def _build_and_post(url, builder, logger, **metadata):
    """Build and post, ad hoc to scraping.

    Arguments:
        url type: str
        builder: story_builder.StoryBuilder instance
        logger: logging.getLogger instance

    Returns: record of post to '/stories' if successful, else {}
    """
    story = builder.assemble_content(url, category='/stories', **metadata)
    # TODO for GDELT: we should either get titles from GDELT server or
    # check url (where?) before grabbing content.  Then can delete this:
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

def _harvest_records(wires):
    """Retrieve urls and associated metadata."""
    records = []
    if 'gdelt' in wires:
        records += _harvest_gdelt()
    if 'newsapi' in wires:
        records += _harvest_newsapi()
    return records

def _harvest_gdelt():
    """"Retrieve urls and metadata from the GDELT service."""
    data = requests.get(WIRE_URLS['gdelt'])
    results = data.json()['results']
    for r in results:
            url = r.pop('SOURCEURL')
            r.update({'url': url})
    random.shuffle(results)
    return results

def _harvest_newsapi():
    """"Retrieve urls and metadata from the NewsAPI service."""
    with open(OUTLETS_FILE,'r') as f:
        outlets = [line.strip() for line in f]
    random.shuffle(outlets)
    
    records = []
    for outlet in outlets:
        payload = {
            'sources': outlet,
            'from': FROM_DATE.isoformat(),
            'apiKey': config.NEWS_API_KEY
        }
        try:
            data = requests.get(WIRE_URLS['newsapi'], params=payload)
            articles = data.json()['articles']
        except Exception:
            continue
        for article in articles:
            metadata = {k:v for k,v in article.items() if k in
                        ('url', 'title', 'description')}
            try:
                metadata.update({
                    'publication_date': article['publishedAt']
                })
            except KeyError:
                pass
            records.append(metadata)
    return records

def _build_logger(directory=EXCEPTIONS_DIR, logfile=LOGFILE):
    logger = logging.getLogger(__name__)
    if not os.path.exists(directory):
        os.makedirs(directory)
    trfh = handlers.TimedRotatingFileHandler(
        os.path.join(directory, logfile), when='D')
    logger.addHandler(trfh)
    return logger

def _signal_handler(*args):
    print('KeyboardInterrupt: Writing logs before exiting...')
    logging.shutdown()
    sys.exit(0)
        
if __name__ == '__main__':
    known_wires = set(WIRE_URLS.keys())
    wires = set([w.lower() for w in sys.argv[1:]])
    if wires:
        unknown = wires.difference(known_wires)
        if unknown:
            print('Newswires {} not recognized'.format(unknown))
        wires = wires.intersection(known_wires)
        print('Proceeding with wires: {}'.format(wires))
    else:
        print('Proceeding with all known wires: {}'.format(known_wires))
        print('Or you can specify a subset of newsires from above list.')
        print('Usage: python news_scraper.py [newswire1] [newswire2] ...')
        wires = known_wires
    scrape(wires)
