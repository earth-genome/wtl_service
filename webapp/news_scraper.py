"""Process current stories from a news wire.

External class: Scrape
External method: __call__

The class is to be called by an RQ worker, scheduled within an asyncio
event loop.

Outputs:
    All stories and their metadata are uploaded to Firebase (STORY_SEEDS).

    After classification, the best candidate stories are sent to
    WhereToLook ('/WTL') on STORY_SEEDS.  

    Exceptions are logged.

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
import asyncio
import datetime
import os
import signal
import sys
import time

from watson_developer_cloud import WatsonApiException

import harvest_urls
import request_thumbnails
from story_seeds.story_builder import story_builder
from story_seeds.utilities import firebaseio
from story_seeds.utilities import log_utilities
import track_urls

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
        session: An aiohttp.ClientSession created within __call__
        

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
            records = self._gather_records(wires)

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

        Outputs: Accepted stories upload to '/WTL'

        Returns: None
        """
        url = record.pop('url')
        self.url_tracker.add(url, time.time())
        try:
            story = self.builder.assemble_content(url, category='/stories',
                                                  **record)
        except WatsonApiException as e:
            self.logger.warning('Assembling content: {}:\n{}'.format(e, url))
            return

        classification, probability = self.builder.run_classifier(story)
        story.record.update({'probability': probability})
        
        if classification == 1:
            story = self.builder.run_geolocation(story)
            if self.thumbnail_grabber:
                try:
                    loc = story.record['core_location']
                    thumbnail_urls = await self.thumbnail_grabber(
                        self.session, loc['lat'], loc['lon'])
                    story.record.update({'thumbnails': thumbnail_urls})
                except (KeyError, aiohttp.ClientError) as e:
                    self.logger.warning('Thumbnails: {}:\n{}'.format(e, url))
            try:
                themes = await self._identify_themes(story.record['text'])
                story.record.update({'themes': themes})
            except aiohttp.ClientError as e:
                self.logger.warning('Themes: {}:\n{}'.format(e, url))

            # Experiment on sentiment:
            if 'water' in story.record.get('themes', {}):
                try:
                    sentiment = story_builder.extract_text.get_sentiment(url)
                    story.record.update({'sentiment': sentiment})
                except WatsonApiException as e:
                    self.logger.warning('Sentiment: {}:\n{}'.format(e, url))
                    
            STORY_SEEDS.put('/WTL', story.idx, story.record)
        return 
                             
    def _gather_records(self, wires):
        """Retrieve urls and associated metadata."""
        records = []
        if 'gdelt' in wires:
            try:
                records += harvest_urls.gdelt()
            except Exception as e:
                self.logger.warning('GDelt: {}:\n{}'.format(e))
        if 'newsapi' in wires:
            try:
                records += harvest_urls.newsapi()
            except Exception as e:
                self.logger.warning('NewsAPI: {}:\n{}'.format(e))
                
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
