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

import aiohttp
import argparse
import asyncio
import datetime
import os
import random
import signal
import sys

import requests

import config
import firebaseio
from story_builder import story_builder

from grab_imagery import log_utilities
from grab_imagery.landsat import thumbnail_grabber
from thumbnails import request_thumbnails

WIRE_URLS = {
    'newsapi': 'https://newsapi.org/v2/everything',
    'gdelt': 'https://gdelt-seeds.herokuapp.com/urls'
}
OUTLETS_FILE = 'newsapi_outlets.txt'

THUMBNAIL_GRABBERS = {
    'landsat': thumbnail_grabber.ThumbnailGrabber(),
    'planet': request_thumbnails.request_thumbnails
}

STORY_SEEDS = firebaseio.DB(firebaseio.FIREBASE_URL)

EXCEPTIONS_DIR = os.path.join(os.path.dirname(__file__),
                              'NewsScraperExceptions_logs')
LOGFILE = 'newswire' + datetime.date.today().isoformat() + '.log'

class Scrape(object):

    def __init__(
        self,
        batch_size=100,
        builder=story_builder.StoryBuilder(),
        grabber=THUMBNAIL_GRABBERS['landsat'],
        logger=log_utilities.build_logger(EXCEPTIONS_DIR, LOGFILE,
                                          logger_name='news_scraper')):
        self.batch_size = batch_size
        self.builder = builder
        self.grabber = grabber
        self.logger = logger
        
                 
    async def __call__(self, wires):
        """Process urls from wires."""
        signal.signal(signal.SIGINT, log_utilities.signal_handler)

        async with aiohttp.ClientSession() as self.session:
            records = _harvest_records(wires)
            print('{} news stories harvested.'.format(len(records)))

            while records:
                batch = records[-self.batch_size:]
                tasklist = [self._build(**r) for r in batch]
                results = await asyncio.gather(*tasklist,
                                               return_exceptions=True)
                self._log_exceptions(results)
                del records[-self.batch_size:]
                print('Batch of {} done\n'.format(self.batch_size))

        print('complete')
        return

    async def _build(self, **record):
        """Build and post, ad hoc to scraping.

        Returns: record of post to '/stories' if successful, else {}
        """
        url = record.pop('url')
        try:
            story = self.builder.assemble_content(url, category='/stories',
                                              **record)
            if STORY_SEEDS.check_known(story):
                return {}
        except Exception:
            self.logger.exception('Assemble content: {}'.format(url))

        clf, prob = self.builder.run_classifier(story)
        story.record.update({'probability': prob})
        if clf == 1:
            story.record.update({
                'themes': self.builder.identify_themes(story)
            })
            story = self.builder.run_geoclustering(story)
            try:
                centroid = _pull_centroid(story)
            except KeyError:
                self.logger.exception('Centroid: {}'.format(url))
            try: 
                thumbnail_urls = await self.grabber(
                    self.session, centroid['lat'], centroid['lon'])
                story.record.update({'thumbnails': thumbnail_urls})
            except Exception:
                self.logger.exception('Thumbnails: {}'.format(url))
            try:
                STORY_SEEDS.put('/WTL', story.idx, story.record)            
            except Exception:
                self.logger.exception('Upload to WTL: {}'.format(url))
            story.record.pop('core_locations')
        story.record.pop('text')
        story.record.pop('keywords')
        try:
            post = STORY_SEEDS.put('/stories', story.idx, story.record)
        except:
            self.logger.exception('Upload to STORYSEEDS: {}'.format(url))
        return post

    def _log_exceptions(self, results):
        """Log exceptions returned from asyncio.gather.

        These are *unexpected* exceptions, not otherwise handled in _build.
        """
        for r in results:
            try:
                raise r
            except TypeError:  # raised if r isn't raisable
                pass
            except:
                print('Logging exception from gather: {}.'.format(r))
                self.logger.exception(repr(r))
                
def _pull_centroid(story):
    """Retrieve centroid for highest-scored cluster in story."""
    clusters = story.record['clusters']
    if not clusters:
        raise KeyError('No geoclusters found.')
    sorted_by_score = sorted(
                [(c['centroid'], c['score']) for c in clusters],
                key=lambda s: s[1])
    centroid = next(reversed(sorted_by_score))[0]
    return centroid
    
def _harvest_records(wires):
    """Retrieve urls and associated metadata."""
    records = []
    if 'gdelt' in wires:
        records += _harvest_gdelt()
    if 'newsapi' in wires:
        records += _harvest_newsapi()
    random.shuffle(records)
    return records

def _harvest_gdelt():
    """"Retrieve urls and metadata from the GDELT service."""
    data = requests.get(WIRE_URLS['gdelt'])
    results = [{'url': r['SOURCEURL'], 'GLOBALEVENTID': r['GLOBALEVENTID']}
               for r in data.json()['results']]
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
            'from': datetime.date.today().isoformat(),
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

        
if __name__ == '__main__':
    known_wires = set(WIRE_URLS.keys())
    parser = argparse.ArgumentParser(
        description='Scrape newswires for satellite-relevant stories.'
    )
    parser.add_argument(
        '-w', '--wires',
        type=str,
        nargs='*',
        default=known_wires,
        help='One or more newswires from {}'.format(known_wires)
    )
    parser.add_argument(
        '-t', '--thumbnail_source',
        type=str,
        default='landsat',
        help='Source of thumbnails for posted stories, from {}'.format(
            set(THUMBNAIL_GRABBERS.keys()))
    )
    parser.add_argument(
        '-b', '--batch_size',
        type=int,
        default=100,
        help='Number of records to process together asynchronously.'
    )
    args = parser.parse_args()
    wires = set([w.lower() for w in args.wires])
    unknown = wires.difference(known_wires)
    if unknown:
        print('Newswires {} not recognized'.format(unknown))
    wires = wires.intersection(known_wires)
    print('Proceeding with wires: {}'.format(wires))

    loop = asyncio.get_event_loop()
    scrape = Scrape(
        batch_size=args.batch_size,
        grabber=THUMBNAIL_GRABBERS[args.thumbnail_source])
    loop.run_until_complete(scrape(wires))
