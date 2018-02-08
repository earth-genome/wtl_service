# TODO: import routines from news-scrape/webapp/scraper/main.py

import requests
import datetime

import config
import story_maker
import firebaseio

import pdb

BASE_URL = 'https://newsapi.org/v1/articles'
with open('newsapi_outlets.txt','r') as f:
    OUTLETS = [line.strip() for line in f]

# single outlet for testing
# OUTLETS = OUTLETS[-1]

def scrape():

    storyseeds = firebaseio.DB(config.FIREBASE_URL)
    logname = 'newsapi'+datetime.date.today().isoformat()+'.log'
    log = open(logname,'a')
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
            log.write('Call for {} to NewsAPI:\n'.format(outlet))
            log.write('Exception: {}\n'.format(e))
            continue

        for article in articles:
            try: 
                metadata = {
                    'url': article['url'],
                    'outlet': outlet,
                    'title': article['title'],
                    'description': article['description'],
                    'date': article['publishedAt']
                }
                story = story_maker.new_story(
                    category='/stories', **metadata)
                if not storyseeds.check_known(story):
                    print(metadata['url'])
                    story_maker.add_facilities(story)
                    storyseeds.put_item(story)
                    if story.record['locations'] != 'Unlocated':
                        geoloc = story_maker.new_story(
                            category='/geolocated', **story.record)
                        storyseeds.put_item(geoloc)
            except Exception as e:
                log.write('Article {}\n'.format(url))
                log.write('Exception: {}\n'.format(e))
                continue
                    
    log.close()
    print('complete')
    return

if __name__ == '__main__':
    scrape()
