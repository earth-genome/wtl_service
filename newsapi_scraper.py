"""Process current stories from NewsAPI.

External function:  scrape()

Usage from main: python newsapi_scraper.py

Outputs:
    All stories and their NewsAPI metadata are uploaded to Firbase
    (STORY_SEEDS).

    Stories are classified and the best candidates sent to the WhereToLook
    feed, currently logged as jsons in the FEED_DIR.

    Exceptions are logged in EXCEPTION_DIR.

The CLASSIFIER variable determines the classifier via the module accessed,
with the expectation that the instantiation loads the most 
recently pickled model.  The CLASSIFER has method classify_story() that
operates on an instance of the firebaseio.DBItem class. See
check_for_feed() below.

"""

import datetime
import json
import os
import random

import requests

import config
import extract_text
import firebaseio
from naivebayes import naivebayes

CLASSIFIER = naivebayes.NBTextClassifier()

#BASE_URL = 'https://newsapi.org/v2/everything'
BASE_URL = 'https://newsapi.org/v1/articles'

with open('newsapi_outlets.txt','r') as f:
    OUTLETS = [line.strip() for line in f]
random.shuffle(OUTLETS)

STORY_SEEDS = firebaseio.DB(config.FIREBASE_URL)
EXCEPTION_DIR = 'NewsAPIexception_logs'
FEED_DIR = 'NewsAPI_WTLfeeds'

import pdb

def scrape():

    except_log = ''
    feed = {}
    for outlet in OUTLETS:
        print("\n%s\n" % outlet)
        payload = {
            'source': outlet,
            #'from': datetime.date.today().isoformat(),
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
            try:
                url = article['url']
                metadata = {
                    'url': url,
                    'outlet': outlet,
                    'title': article['title'],
                    'description': article['description'],
                    'publication_date': article['publishedAt']
                }
                story = firebaseio.DBItem('/stories', None, metadata)
                if not STORY_SEEDS.check_known(story):
                    STORY_SEEDS.put_item(story)
                    feed.update(check_for_feed(story))                    
            except Exception as e:
                except_log += 'Article {}\n'.format(article['url'])
                except_log += 'Exception: {}\n'.format(repr(e))
                continue
    if feed != {}:
        log_feed(feed)
    if except_log != '':
        log_exceptions(except_log)
    print('complete')
    return

def check_for_feed(story):
    """Determine whether story belongs in the WTL feed.

    Returns: None or dict-formatted story data to add to feed.
    """
    url = story.record['url']
    story.record.update(extract_text.get_parsed_text(url))
    classification, prob = CLASSIFIER.classify_story(story)
    if classification == 1:
        story.record.update({'probability': prob})
        story.record.pop('text')
        story.record.pop('keywords')
        story_feed = {story.idx: story.record}
        print('Added to feed @ prob {:.2f}: {}\n'.format(prob, url))
    else:
        story_feed = {}
        print('Declined @ prob {:.2f}: {}\n'.format(prob, url))
    return story_feed

def log_feed(feed, dir=FEED_DIR):
    """Write feed to json file."""
    if not os.path.exists(dir):
        os.makedirs(dir)
    feedfile = os.path.join(dir, datetime.datetime.now().isoformat()+'.json')
    with open(feedfile, 'a') as f:
        json.dump(feed, f, indent=4)
    return

def log_exceptions(log, dir=EXCEPTION_DIR):
    """Write exceptions to file."""
    if not os.path.exists(dir):
            os.makedirs(dir)
    logfile = os.path.join(dir, datetime.date.today().isoformat()+'.log')
    with open(logfile, 'a') as f:
        f.write(log)
    return
        
if __name__ == '__main__':
    scrape()
