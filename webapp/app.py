"""A Flask web app to source stories for the Where to Look (WTL) database.

Story retrieval is handled by web app directly; story build and classification
is pushed to a Redis queue and handled by the worker process in worker.py.
"""

import datetime
import json
import os
import sys

from flask import Flask, request
from flask_restful import inputs
import numpy as np
from rq import Queue

#from story_seeds import firebaseio
#from story_seeds import news_scraper
#from story_seeds import log_utilities
import worker

q = Queue('default', connection=worker.connection, default_timeout=86400)
app = Flask(__name__)


# for help messaging
SCRAPER_ARGUMENTS = {
    'Required arguments': {
        'wires': 'One or more of {}'.format(
                set(news_scraper.WIRE_URLS.keys())
    },
    'Optional arguments': {
        'thumbnail_source': 'One of {}'.format(
            set(news_scraper.THUMBNAIL_GRABBERS.keys()),
        'thumbnail_timeout': 'Integer number of seconds',
        'batch_size': ('Integer number of records to gather for ' +
                       'asynchronous processing.')
    }
}
          

@app.route('/')
def help():
    welcome = ('This web app provides functionality from the following ' + 
        'endpoints, each of which takes required and optional arguments. ' +
        'Hit one of these urls to see specific argument formatting.')
    msg = {
        'Welcome': welcome,
        'Scrape news wires for stories.':
            ''.join((request.url, 'scrape?')),
        'Retrieve stories posted to the WTL database.':
            ''.join((request.url, 'retrieve?'))
    }
    return json.dumps(msg)
  
@app.route('/scrape')
def scrape():
    """Pull images given lat, lon, and scale."""
    msg = _help_msg(
        request.base_url,
        'wires=gdelt&wires=newsapi&thumbnail_source=landsat',
        SCRAPER_ARGUMENTS)

    try:
        wires, kwargs = _parse_scrape_params(args)
    except ValueError as e:
        msg['Exception'] = repr(e)
        return json.dumps(msg)
        
    kwargs['logger'] = log_utilities.get_stream_logger(sys.stderr)

    scraper = news_scraper.Scrape(**kwargs)
    job = q.enqueue_call(
        func=scraper_wrappers.scrape,
            args=(wires,),
            kwargs=kwargs)

    guide = _pulling_guide(request.url_root, db_key, bbox.bounds, **kwargs)
    return json.dumps(guide)

@app.route('/retrieve')
def retrieve():
    """Retrieve records from the WTL database."""
    
    notes = ('Either daysback or start and end dates in form YYYY-MM-DD ' +
             'are required. Daysback will override start and end dates. ' +
             'Expect up to hundreds of records per day requested.')
    msg = _help_msg(
        request.base_url, 'daysback=3&start=2018-09-27&end=2018-09-22', notes)

    try:
        startDate, endDate = _parse_daysback(args)
    except ValueError:
        try: 
            startDate, endDate = _parse_dates(args)
        except (ValueError, TypeError) as e:
            msg['Exception'] = repr(e)
            return json.dumps(msg)

    stories = news_scraper.STORY_SEEDS.grab_stories(
        category='/WTL', startDate=startDate, endDate=endDate)

    return json.dumps([_clean(story) for story in stories])

def _clean(story):
    """Extract story data for web presentation."""
    base_url = 'http://earthrise-imagery.herokuapp.com/retrieve-story?'
    try:
        rec = {'title': story.record['title']}
    except:
        rec = {}
    rec.update({
            'url': story.record['url']
            'Full record': base_url + 'idx={}'.format(story.idx)
    })
    return rec
    
# Argument parsing functions

def _parse_scrape_params(args):
    """Parse url for news wires, thumbnail source, and story batch size."""
    
    wires = args.getlist('wires')
    kwargs = {
        'batch_size' = args.get('batch_size', type=int),
        'thumbnail_source' = args.get('thumbnail_source', type=str),
        'thumbnail_timeout' = args.get('thumbnail_timeout', type=int)
    }
    
    if not wires or not set(wires) <= set(news_scraper.WIRE_URLS.keys()):
        raise ValueError('Supported wire are {}'.format(
            set(news_scraper.WIRE_URLS.keys()))
    
    known_grabbers = set(news_scraper.THUMBNAIL_GRABBERS.keys())
    if thumbnail_source and thumbnail_source not in known_grabbers:
        raise ValueError('thumbnail_source must be from {}'.format(
                known_grabbers))
    
    return wires, kwargs

def _parse_daysback(args):
    """Parse number of days from today and convert to start/end dates."""
    daysback = args.get('daysback', type=int)
    if not daysback:
        raise ValueError
    today = datetime.date.today()
    end = today + datetime.timedelta(days=1)
    start = today - datetime.timedelta(days=daysback)
    return start.isoformat(), end.isoformat()

def _parse_dates(args):
    """Parse dates from url arguments."""
    start = args.get('start', type=str)
    end = args.get('end', type=str)
    
    # Check date formatting. Will raise ValueError if misformatted or
    # TypeError if one of start/end is None.
    start = datetime.datetime.strptime(start, '%Y-%m-%d').date()
    end = datetime.datetime.strptime(end, '%Y-%m-%d').date()
    
    return start.isoformat(), end.isoformat()

# Help messaging

def _help_msg(base_url, url_args, notes):
    msg = {
        'Usage': '{}?{}'.format(base_url, url_args),
        'Notes': notes
    }
    return msg

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0')
