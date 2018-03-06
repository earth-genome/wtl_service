"""Process current stories from NewsAPI.

The endpoint for a processed story is a Firebase database story item,
including possibly geolocated facilities identified in the stories.

External function:  scrape()
Or from main: python newsapi_scraper.py

"""

import os

import datetime
import random
import requests

import config
import story_maker
import firebaseio

BASE_URL = 'https://newsapi.org/v1/articles'
with open('newsapi_outlets.txt','r') as f:
    OUTLETS = [line.strip() for line in f]
random.shuffle(OUTLETS)
LOG_DIR = 'NewsAPIlogs'

def scrape():

    storyseeds = firebaseio.DB(config.FIREBASE_URL)
    log = ''
    for outlet in OUTLETS:
        # TODO: Figure out if calling "top" vs. "latest" gets us more than 10
		# stories at a time for each outlet
        print("\n%s\n" % outlet)
        payload = {
            'source': outlet,
            'apiKey': config.NEWS_API_KEY
        }
        try: 
            data = requests.get(BASE_URL, params=payload)
            articles = data.json()['articles']
        except Exception as e:
            log += 'Call for {} to NewsAPI:\n'.format(outlet)
            log += 'Exception: {}\n'.format(repr(e))
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
                story = firebaseio.DBITEM('/stories', None, metadata)
                if not storyseeds.check_known(story):
                    storyseeds.put_item(story)
                    print(url)
                    # TODO: add classifier / pipe output appropriately
                    #full_record = extract_text.get_parsed_text(metadata['url'])
            except Exception as e:
                log += 'Article {}\n'.format(article['url'])
                log += 'Exception: {}\n'.format(repr(e))
                continue
    if log != '':
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)
        logfile = os.path.join(LOG_DIR,
                               datetime.date.today().isoformat()+'.log')
        with open(logfile,'a') as f:
            f.write(log)               
    print('complete')
    return

if __name__ == '__main__':
    scrape()
