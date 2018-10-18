"""Process current stories from a news wire.

External class: Scrape
External method: __call__

The class is to be called by an RQ worker, scheduled within an asyncio
event loop.

Outputs:
    All stories and their metadata are uploaded to Firbase (STORY_SEEDS).

    After classification, the best candidate stories are sent to
    WhereToLook ('/WTL') on STORY_SEEDS.  

    Exceptions are logged.

Basic usage from main (deprecated):
$ python news_scraper.py
For syntax, run:
$ python news_scraper.py -h

Notes: The class attribute batch_size determines the number of records
gathered for asynchronous processing. For each story selected for the 
WTL database, a request for thumbnails is posted to the image service,
at which point the story builder reliquishes control to the event
loop. The selected story will then be at the end of the processing queue,
and control will return only after all the records in the batch have
been touched at least once. If the scrape is interrupted during a batch,
all stories selected to WTL (those we want to capture) will be lost.

A large batch is advantageous because stories continue to be processed while
awaiting thumbnails for the small subset of selected stories. A small
batch means fewer stories lost when processing is interrupted. As of writing,
I am working with batch sizes of 100 or 200 for planet thumbnails; 20 is
sufficient for landsat.

Another issue here is the aiohttp timeout. By default it is 300s, which is
too short becuase the long async queue may lead to long times between
revisits to any given process. At the same time we don't want it to be
infinite because very ocassionally a call to planet for thumbnails will hang.
In limited testing I have arrived at 1200 seconds for batch_size=100 and
two thumbnail worker processes. That also worked for batch_size=200 and
four thumbnail worker processes.

"""

import aiohttp
import argparse
import asyncio
import datetime
import os
import random
import signal
import sys
import time

import requests

import request_thumbnails
from story_seeds import config
from story_seeds.story_builder import story_builder
from story_seeds.utilities import firebaseio
from story_seeds.utilities import log_utilities
import track_urls

WIRE_URLS = {
    'newsapi': 'https://newsapi.org/v2/everything',
    'gdelt': 'https://gdelt-seeds.herokuapp.com/urls'
}
OUTLETS_FILE = 'newsapi_outlets.txt'

STORY_SEEDS = firebaseio.DB(firebaseio.FIREBASE_URL)

THEMES_URL = 'https://www.floydlabs.com/serve/earthrise/projects/themes'

# Logging when running locally from main:
EXCEPTIONS_DIR = os.path.join(os.path.dirname(__file__), 'NewsScraperLogs')
LOGFILE = 'newswire' + datetime.date.today().isoformat() + '.log'

# The asyncio event scheduling cannot be pickled and therefore cannot
# be Redis-queued. From app.py we must enqueue a function that, as
# part of its process, establishes the event loop:

def scraper_wrapper(wires, **kwargs):
    """Instantiate, schedule, and call the Scrape process."""
    scraper = Scrape(**kwargs)
    looped = loop(scraper)
    looped(wires)
    return

def loop(function):
    """Scheduler for async processing."""
    def scheduled(*args, **kwargs):
        loop = asyncio.get_event_loop()
        task = asyncio.ensure_future(function(*args, *kwargs))
        output = loop.run_until_complete(task)
        return output
    return scheduled

class Scrape(object):
    """
    Scrape news wires for stories that can be enhanced by satellite imagery.
    
    Attributes:
        batch_size: Number of records to process together asynchronously.
        thumbnail_grabber: Class instance to pull thumbnail images.
        themes_url: Web app endpoint for themes classifier.
        timeout: Timeout for aiohttp requests. (See notes above.)
        url_tracker: Class instance to track scraped urls.
        logger: Exception logger.
        builder: Class instance to extract, evaluate, and post story from
            url.
        

    External method:
        __call__: Process urls from wires.
    """

    def __init__(
        self,
        batch_size=100,
        thumbnail_source=None,
        themes_url=THEMES_URL,
        http_timeout=1200,
        url_tracker=track_urls.TrackURLs(),
        logger=log_utilities.get_stream_logger(sys.stderr),
        **kwargs):
        
        self.batch_size = batch_size
        if thumbnail_source:
            self.thumbnail_grabber = request_thumbnails.RequestThumbnails(
                thumbnail_source)
        else:
            self.thumbnail_grabber = None
        self.themes_url = themes_url
        self.timeout = aiohttp.ClientTimeout(total=http_timeout)
        self.url_tracker = url_tracker
        self.logger = logger
        self.builder = story_builder.StoryBuilder(**kwargs)

    async def __call__(self, wires):
        """Process urls from wires."""
        signal.signal(signal.SIGINT, log_utilities.signal_handler)

        async with aiohttp.ClientSession(timeout=self.timeout) as self.session:
            records = self._harvest_records(wires)

            while records:
                batch = records[-self.batch_size:]
                tasklist = [self._build(**r) for r in batch]
                results = await asyncio.gather(*tasklist,
                                               return_exceptions=True)
                self._log_exceptions(results)
                del records[-self.batch_size:]
                print('Batch of {} done\n'.format(self.batch_size), flush=True)

        print('complete')
        return

    async def _build(self, **record):
        """Build and post, ad hoc to scraping.

        Outputs: Story uploads to '/WTL' and/or '/stories', if successful

        Returns: None
        """
        url = record.pop('url')
        self.url_tracker.add(url, time.time())
        story = self.builder.assemble_content(url, category='/stories', **record)

        classification, probability = self.builder.run_classifier(story)
        story.record.update({'probability': probability})
        
        if classification == 1:
            try:
                themes = await self._identify_themes(story.record['text'])
                story.record.update({'themes': themes})
            except Exception as e:
                self.logger.warning('Themes: {}\n{}'.format(e, url))
                    
            story = self.builder.run_geoclustering(story)
            if self.thumbnail_grabber:
                try:
                    centroid = _pull_centroid(story)
                    thumbnail_urls = await self.thumbnail_grabber(
                        self.session, centroid['lat'], centroid['lon'])
                    story.record.update({'thumbnails': thumbnail_urls})
                except KeyError as e:
                    self.logger.warning('{}:\n{}'.format(e, url))
            STORY_SEEDS.put('/WTL', story.idx, story.record)
            story.record.pop('core_locations', None)
            
        story.record.pop('text', None)
        story.record.pop('keywords', None)
        STORY_SEEDS.put('/stories', story.idx, story.record)
        
        return 
                             
    def _harvest_records(self, wires):
        """Retrieve urls and associated metadata."""
        records = []
        if 'gdelt' in wires:
            records += _harvest_gdelt()
        if 'newsapi' in wires:
            records += _harvest_newsapi()
        fresh_urls = self.url_tracker.find_fresh([r['url'] for r in records])
        records = [r for r in records if r['url'] in fresh_urls]
        return records

    async def _identify_themes(self, text):
        """Query an app-based themes classifier."""
        async with self.session.post(self.themes_url,
                                     data={'text':text},
                                     raise_for_status=True) as resp:
            themes = await resp.json()
        return themes

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
                self.logger.exception('Logging exception from gather.')
                
def _pull_centroid(story):
    """Retrieve centroid for highest-scored cluster in story."""
    clusters = story.record.get('clusters')
    if not clusters:
        raise KeyError('No geoclusters found.')
    sorted_by_score = sorted(
                [(c['centroid'], c['score']) for c in clusters],
                key=lambda s: s[1])
    centroid = next(reversed(sorted_by_score))[0]
    return centroid
    
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
        choices=known_wires,
        default=known_wires,
        help='One or more newswires from {}'.format(known_wires)
    )
    parser.add_argument(
        '-t', '--thumbnail_source',
        type=str,
        choices=set(request_thumbnails.PROVIDER_PARAMS.keys()),
        help='Source of thumbnails for posted stories, from {}'.format(
            set(request_thumbnails.PROVIDER_PARAMS.keys()))
    )
    parser.add_argument(
        '-to', '--http_timeout',
        type=int,
        help='Timeout for (esp. thumbnail) http requests in seconds.'
    )
    parser.add_argument(
        '-b', '--batch_size',
        type=int,
        help='Number of records to process together asynchronously.'
    )
    kwargs = {k:v for k,v in vars(parser.parse_args()).items()
              if v is not None}
    wires = kwargs.pop('wires')
    kwargs['logger'] = log_utilities.build_logger(EXCEPTIONS_DIR, LOGFILE)
    
    scraper_wrapper(wires, **kwargs)
