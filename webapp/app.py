"""A Flask web app to source stories for the Where to Look (WTL) database.

Story retrieval is handled by web app directly; story build and classification
is pushed to a Redis queue and handled by the worker process in worker.py.
"""

import datetime
import json
import os
import sys
import urllib.parse

from flask import Flask, request
from flask_restful import inputs
import numpy as np
from rq import Queue

import news_scraper
import request_thumbnails
from story_seeds.utilities import firebaseio
from story_seeds.utilities import log_utilities
import worker

q = Queue('default', connection=worker.connection, default_timeout=86400)
app = Flask(__name__)

@app.route('/')
def welcome():
    welcome = ('This web app provides functionality from the following ' + 
        'endpoints, each of which takes required and optional arguments. ' +
        'Hit one of these urls to see specific argument formatting.')
    msg = {
        'Welcome': welcome,
        'Scrape news wires for stories':
            ''.join((request.url, 'scrape?')),
        'Retrieve stories posted to the WTL database':
            ''.join((request.url, 'retrieve?')),
        'Retrieve a single story record from the WTL database':
            ''.join((request.url, 'retrieve-story?')),
    }
    return json.dumps(msg)
  
@app.route('/scrape')
def scrape():
    """Pull images given lat, lon, and scale."""
    msg = _help_msg(
        request.base_url,
        'wires=gdelt&wires=newsapi&thumbnail_source=landsat',
        _format_scraper_args())

    try:
        wires, kwargs = _parse_scrape_params(request.args)
        print('Initiating scrape with wires {} and params {}'.format(
            wires, kwargs), flush=True)
    except ValueError as e:
        msg['Exception'] = repr(e)
        return json.dumps(msg)

    job = q.enqueue_call(
        func=news_scraper.scraper_wrapper, args=(wires,), kwargs=kwargs)

    return json.dumps(_format_scraping_guide())

@app.route('/retrieve')
def retrieve():
    """Retrieve records from the WTL database."""
    
    notes = ('Either daysback or start and end dates in form ' +
             'start=YYYY-MM-DD&end=YYYY-MM-DD are required.' +
             'Expect up to hundreds of records per day requested.')
    msg = _help_msg(request.base_url, 'daysback=3', notes)

    try:
        startDate, endDate = _parse_daysback(request.args)
    except ValueError:
        try: 
            startDate, endDate = _parse_dates(request.args)
        except (ValueError, TypeError) as e:
            msg['Exception'] = repr(e)
            return json.dumps(msg)

    stories = news_scraper.STORY_SEEDS.grab_stories(
        category='/WTL', startDate=startDate, endDate=endDate)

    return json.dumps([_clean(story) for story in stories])

@app.route('/retrieve-story')
def retrieve_story():
    """Retrieve a story record from the WTL database."""

    msg = _help_msg(request.base_url,
                    'idx=Index of the story in the database', '')
    try:
        idx  = _parse_index(request.args)
    except ValueError as e:
        msg['Exception'] = repr(e)
        return json.dumps(msg)

    record = news_scraper.STORY_SEEDS.get('/WTL', idx)
    return json.dumps({idx: record})

def _clean(story):
    """Curate story data for web presentation."""
    try:
        title = story.record['title']
    except KeyError:
        title = ''
    rec = {
        'Source url': story.record['url'],
        'title': title,
        'Full record': request.url_root + 'retrieve-story?idx={}'.format(
            urllib.parse.quote(story.idx))
    }
    return rec
    
# Argument parsing functions

def _parse_scrape_params(args):
    """Parse url for news wires, thumbnail source, and story batch size."""
    
    wires = args.getlist('wires')
    kwargs = {
        'batch_size': args.get('batch_size', type=int),
        'parse_images': args.get('parse_images', type=inputs.boolean),
        'thumbnail_source': args.get('thumbnail_source'),
        'thumbnail_timeout': args.get('thumbnail_timeout')
    }
    
    if not wires or not set(wires) <= set(news_scraper.WIRE_URLS.keys()):
        raise ValueError('Supported wire are {}'.format(
            set(news_scraper.WIRE_URLS.keys())))
    
    known_grabbers = set(request_thumbnails.PROVIDER_PARAMS.keys())
    tns = kwargs['thumbnail_source']
    if tns and tns not in known_grabbers:
        raise ValueError('thumbnail_source must be from {}'.format(
            known_grabbers))

    kwargs = {k:v for k,v in kwargs.items() if v is not None}
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
    start = args.get('start')
    end = args.get('end')
    
    # Check date formatting. Will raise ValueError if misformatted or
    # TypeError if one of start/end is None.
    start = datetime.datetime.strptime(start, '%Y-%m-%d').date()
    end = datetime.datetime.strptime(end, '%Y-%m-%d').date()
    
    return start.isoformat(), end.isoformat()

def _parse_index(args):
    """Parse url arguments for story index."""
    idx = args.get('idx')
    if not idx:
        raise ValueError('A story index is required.')
    return idx

# Help messaging
    
def _help_msg(base_url, url_args, notes):
    msg = {
        'Usage': '{}?{}'.format(base_url, url_args),
        'Notes': notes
    }
    return msg

def _format_scraper_args():
    """Produce a dict explaining scraper args for help messaging."""
    scraper_args = {
        'Required arguments': {
            'wires': 'One or more of {}'.format(
                set(news_scraper.WIRE_URLS.keys()))
        },
        'Optional arguments': {
            'thumbnail_source': 'One of {}'.format(
                set(request_thumbnails.PROVIDER_PARAMS.keys())),
            'thumbnail_timeout': 'Integer number of seconds',
            'batch_size': ('Integer number of records to gather for ' +
                'asynchronous processing.'),
            'parse_images': ('True/False whether to include images from ' +
                             'news stories in their classification.') 
        }
    }
    return scraper_args

def _format_scraping_guide():
    """Produce a message to return when scrape is called."""
    guide = {
        'Scraping': 'Now. Records will be continuously posted to WTL.',
        'Retrieve records': '{}'.format(request.url_root + 'retrieve')
    }
    return guide

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0')
