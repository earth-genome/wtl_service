"""Process current stories from NewsAPI.

External function:  scrape()

Usage from main: python newsapi_scraper.py

Outputs:
    All stories and their NewsAPI metadata are uploaded to Firbase
    (STORY_SEEDS).

    Stories are classified and the best candidates sent to the WhereToLook
    feed, currently logged as jsons in the FEED_DIR.

    Exceptions are logged in EXCEPTION_DIR.

The CLASSIFIER variable loads a pickled classifier, which has method
classify_story() that operates on an instance of the firebaseio.DBItem class.
See use in vet_for_feed() below.

"""

import datetime
import json
import os
import random
import signal
import sys

import requests
from sklearn.externals import joblib

import config
import extract_text
import firebaseio

CLASSIFIER = joblib.load('naivebayes/NBtext_models/latest_model.pkl')

BASE_URL = 'https://newsapi.org/v2/everything'
#BASE_URL = 'https://newsapi.org/v2/top-headlines'

with open('newsapi_outlets.txt','r') as f:
    OUTLETS = [line.strip() for line in f]
random.shuffle(OUTLETS)

STORY_SEEDS = firebaseio.DB(config.FIREBASE_URL)

EXCEPTION_DIR = 'NewsAPIexception_logs'
FEED_DIR = 'NewsAPI_WTLfeeds'

def scrape():

    except_log = ''
    feed = {}

    def signal_handler(*args):
        print('KeyboardInterrupt: Writing logs before exiting...')
        log_feed(feed)
        log_exceptions(except_log)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    for outlet in OUTLETS:
        print("\n%s\n" % outlet)
        
        payload = {
            'sources': outlet,
            'from': datetime.date.today().isoformat(),
            'apiKey': config.NEWS_API_KEY
        }
        try:
            data = requests.get(BASE_URL, params=payload)
            articles = data.json()['articles']
        except Exception as e:
            except_log += 'Call for {} to NewsAPI:\n'.format(outlet)
            except_log += 'Exception: {}\n'.format(repr(e))
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
            try:
                story = firebaseio.DBItem('/stories', None, metadata)
                if not STORY_SEEDS.check_known(story):
                    story, classification = vet_for_feed(story)
                    if classification == 1:
                        feed.update({story.idx: story.record.copy()})
                        STORY_SEEDS.put('/WTL', story.idx, story.record)
                    story.record.pop('text')
                    story.record.pop('keywords')
                STORY_SEEDS.put('/stories', story.idx, story.record)
            except Exception as e:
                except_log += 'Article {}\n'.format(article['url'])
                except_log += 'Exception: {}\n'.format(repr(e))
                continue
    log_feed(feed)
    log_exceptions(except_log)
    print('complete')
    return

def vet_for_feed(story):
    """Determine whether story belongs in the WTL feed.

    Returns: Updated story and classification (0/1).
    """
    url = story.record['url']
    story.record.update(extract_text.get_parsed_text(url))
    classification, prob = CLASSIFIER.classify_story(story)
    story.record.update({'probability': prob})
    if classification == 1:
        print('Adding to feed @ prob {:.2f}: {}\n'.format(prob, url))
    else:
        print('Declined @ prob {:.2f}: {}\n'.format(prob, url))
    return story, classification

def log_feed(feed, dir=FEED_DIR):
    """Write feed to json file."""
    if feed == {}:
        return
    if not os.path.exists(dir):
        os.makedirs(dir)
    feedfile = os.path.join(dir, datetime.datetime.now().isoformat()+'.json')
    with open(feedfile, 'a') as f:
        json.dump(feed, f, indent=4)
    return

def log_exceptions(log, dir=EXCEPTION_DIR):
    """Write exceptions to file."""
    if log == '':
        return
    if not os.path.exists(dir):
            os.makedirs(dir)
    logfile = os.path.join(dir, datetime.date.today().isoformat()+'.log')
    with open(logfile, 'a') as f:
        f.write(log)
    return
        
if __name__ == '__main__':
    scrape()
