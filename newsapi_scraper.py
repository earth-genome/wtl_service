"""Process current stories from NewsAPI.

External function:  scrape()

Usage from main: python newsapi_scraper.py

Outputs:
    All stories and their NewsAPI metadata are uploaded to Firbase
    (STORY_SEEDS).

    After classification, the best candidate stories are sent to the
    WhereToLook database.  

    Exceptions are logged in EXCEPTION_DIR.
"""

import datetime
import json
import os
import random
import signal
import sys

import requests

import config
import firebaseio
from logger import log_exceptions
from story_builder import story_builder

BASE_URL = 'https://newsapi.org/v2/everything'
#BASE_URL = 'https://newsapi.org/v2/top-headlines'

with open('newsapi_outlets.txt','r') as f:
    OUTLETS = [line.strip() for line in f]
random.shuffle(OUTLETS)

#FROM_DATE = datetime.date.today() - datetime.timedelta(days=2)
FROM_DATE = datetime.date.today()

STORY_SEEDS = firebaseio.DB(config.FIREBASE_URL)

EXCEPTION_DIR = 'NewsAPIexception_logs'

def scrape():

    except_log = ''

    def signal_handler(*args):
        print('KeyboardInterrupt: Writing logs before exiting...')
        log_exceptions(except_log, directory=EXCEPTION_DIR)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    
    builder = story_builder.StoryBuilder()

    for outlet in OUTLETS:
        print("\n%s\n" % outlet)

        payload = {
            'sources': outlet,
            'from': FROM_DATE.isoformat(),
            'apiKey': config.NEWS_API_KEY
        }
        try:
            data = requests.get(BASE_URL, params=payload)
            articles = data.json()['articles']
        except Exception as e:
            except_log += 'Call for {} to NewsAPI:\n{}\n'.format(outlet,
                                                                 repr(e))
            continue

        for article in articles:
            url = article['url']
            try:
                metadata = {
                    'url': url,
                    'outlet': outlet,
                    'title': article['title'],
                    'description': article['description'],
                    'publication_date': article['publishedAt']
                }
            except KeyError:
                metadata = {
                    'url': url,
                    'outlet': outlet
                }
            story = firebaseio.DBItem('/stories', None, metadata)
            if STORY_SEEDS.check_known(story):
                continue
            
            try:
                story, classification, feed_rec = builder(**metadata)
            except Exception as e:
                except_log += repr(e)
                continue

            if classification == 1:
                try:
                    STORY_SEEDS.put('/WTL', story.idx, story.record)
                except Exception as e:
                    except_log += 'Uploading article {}:\n{}\n'.format(url,
                                                                     repr(e))
                story.record.pop('core_locations')
            story.record.pop('text')
            story.record.pop('keywords')
            try:
                STORY_SEEDS.put('/stories', story.idx, story.record)
            except Exception as e:
                except_log += 'Uploading article {}:\n{}\n'.format(url,
                                                                   repr(e))
    log_exceptions(except_log, directory=EXCEPTION_DIR)
    print('complete')
    return

        
if __name__ == '__main__':
    scrape()
