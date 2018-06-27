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

WIRE_URLS = {
    'newsapi': 'https://newsapi.org/v2/everything',
    'gdelt': 'https://gdelt-seeds.herokuapp.com/urls'
}

# NewsAPI:
OUTLETS_FILE = 'newsapi_outlets.txt'
FROM_DATE = datetime.date.today()

STORY_SEEDS = firebaseio.DB(firebaseio.FIREBASE_URL)

EXCEPTIONS_DIR = os.path.join(os.path.dirname(__file__),
                              'NewsScraperExceptions_logs')
LOGFILE = 'newswire' + datetime.date.today().isoformat() + '.log'

# -- test --
# To test a trial classifier, include this code and one more section below.
import json
#from sklearn.externals import joblib
#TRIAL_CLF = joblib.load('bagofwords/MLPstacker_models/latest_model.pkl')

def comp(story, clf, prob, trial_clf, trial_prob):
    """Write examples where trial and incumbent classifier disagree."""
    if trial_clf != clf:
        disagree = {
                'idx': story.idx,
                'url': story.record['url'],
                'Incumbent classifier': prob,
                'Trial classifier': trial_prob
        }
        with open(datetime.date.today() + 'ClassifierComps.txt', 'a') as f:
            json.dump(disagree, f, indent=4)
    return
# -- end test -- 

def scrape(wires):

    logger = log_utilities.build_logger(EXCEPTIONS_DIR, LOGFILE,
                                        logger_name='news_scraper')
    signal.signal(signal.SIGINT, log_utilities.signal_handler)
    builder = story_builder.StoryBuilder()
    img_grabber = thumbnail_grabber.ThumbnailGrabber(logger=logger)
    records = _harvest_records(wires)
    print('{} news stories harvested.'.format(len(records)))

    for rec in records:
        if 'title' in rec.keys():
            provis_story = firebaseio.DBItem('/stories', None, rec)
            if STORY_SEEDS.check_known(provis_story):
                continue
        url = rec.pop('url')
        try:
            _build_and_post(url, builder, img_grabber, logger, **rec)
        except:
            logger.error(url, exc_info=True)

    print('complete')
    return

def _build_and_post(url, builder, img_grabber, logger, **metadata):
    """Build and post, ad hoc to scraping.

    Arguments:
        url type: str
        builder: story_builder.StoryBuilder instance
        img_grabber: instance to source images and post to cloud storage
        logger: logging.getLogger instance

    Returns: record of post to '/stories' if successful, else {}
    """
    story = builder.assemble_content(url, category='/stories', **metadata)
    # TODO for GDELT: we should either get titles from GDELT server or
    # check url (where?) before grabbing content.  Then can delete this:
    if STORY_SEEDS.check_known(story):
        return {}
    clf, prob = builder.run_classifier(story)

    # -- test -- To test a trial classifier, uncomment this try-except clause:
    #try:
    #    trial_clf, trial_prob = TRIAL_CLF.classify_story(story)
    #    print('Trial clf, prob: {}, {}\n'.format(trial_clf, trial_prob))
    #    comp(story, clf, prob, trial_clf, trial_prob)
    #except:
    #    print('Exception in comp {}'.format(story.idx))
    # -- end test -- 
    
    story.record.update({'probability': prob})
    if clf == 1:
        story.record.update({'themes': builder.identify_themes(story)})
        story = builder.run_geoclustering(story)
        try:
            centroid = _pull_centroid(story)
            thumbnail_urls = img_grabber.source_and_post(
                centroid['lat'], centroid['lon'])
            story.record.update({'thumbnails': thumbnail_urls})
        except KeyError as e:
            logger.error('Centroid coords: {}'.format(url), exc_info=True)
        try: 
            STORY_SEEDS.put('/WTL', story.idx, story.record)            
        except Exception as e:
            logger.error('Uploading to WTL: {}'.format(url), exc_info=True)
        story.record.pop('core_locations')
    story.record.pop('text')
    story.record.pop('keywords')
    return STORY_SEEDS.put('/stories', story.idx, story.record)

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
