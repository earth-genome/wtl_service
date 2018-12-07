"""A Flask web app to source stories for the Where to Look (WTL) database.

Story retrieval is handled by web app directly; story build and classification
is pushed to a Redis queue and handled by the worker process in worker.py.
"""

import datetime
import json
import os
import urllib.parse

from flask import Flask, jsonify, request
from flask_restful import inputs
import numpy as np
import requests
from rq import Queue

import floyd_login
import news_scraper
import request_thumbnails
from story_seeds.utilities import firebaseio
from story_seeds.utilities import log_utilities
import worker

q = Queue('default', connection=worker.connection, default_timeout=86400)
app = Flask(__name__)

KNOWN_THEMES_URL = news_scraper.THEMES_URL + '/known_themes'

FLOYD_INIT_FILE = '.floydexpt'

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
        'Restart serving the Floydhub learned models':
            ''.join((request.url, 'restart-floyd?'))
    }
    return jsonify(msg)
  
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
        return jsonify(msg)

    job = q.enqueue_call(
        func=news_scraper.scraper_wrapper, args=(wires,), kwargs=kwargs)

    return jsonify(_format_scraping_guide())

@app.route('/retrieve')
def retrieve():
    """Retrieve records from the WTL database."""
    msg = _help_msg(
        request.base_url,
        'daysback=3&filterby=scrape_date&themes=water&themes=conflict',
        _format_retrieve_args())

    try:
        themes, kwargs = _parse_retrieve_params(request.args)
    except (ValueError, TypeError) as e:
        msg['Exception'] = repr(e)
        return jsonify(msg)
    
    stories = news_scraper.STORY_SEEDS.grab_stories(category='/WTL', **kwargs)

    if themes:
        stories = [s for s in stories
                   if set(themes).intersection(s.record.get('themes', {}))]

    return jsonify([_clean(s) for s in stories])

@app.route('/retrieve-story')
def retrieve_story():
    """Retrieve a story record from the WTL database."""
    msg = _help_msg(request.base_url,
                    'idx=Index of the story in the database', '')
    try:
        idx  = _parse_index(request.args)
    except ValueError as e:
        msg['Exception'] = repr(e)
        return jsonify(msg)

    record = news_scraper.STORY_SEEDS.get('/WTL', idx)
    return jsonify({idx: record})
    
def _clean(story):
    """Curate story data for web presentation."""
    title = story.record.get('title', '')
    themes = story.record.get('themes', {})
    rec = {
        'Source url': story.record['url'],
        'title': title,
        'themes': themes,
        'Full record': request.url_root + 'retrieve-story?idx={}'.format(
            urllib.parse.quote(story.idx))
    }

    # Experiment on sentiment:
    if 'water' in themes:
        rec.update({'sentiment': story.record.get('sentiment', {})})
    return rec

@app.route('/restart-floyd')
def restart_floyd():
    """Restart the Floydhub job serving our learned models."""
    msg = _help_msg(request.base_url, 'job=22', '')
    try:
        job_name = _parse_job(request.args)
    except ValueError as e:
        msg['Exception'] = repr(e)
        return jsonify(msg)
    try:
        floyd_login.login()
        client = floyd_login.get_client()
        experiments = client.get_all()
    except FloydException as e:
        msg['Exception'] = repr(e)
        return jsonify(msg)

    _halt_serving(client, experiments)
    try:
        to_serve = next(e for e in experiments if job_name in e.name)
        status = client.restart(to_serve.id)
    except (FloydException, StopIteration) as e:
        msg['Exception'] = repr(e)
        return jsonify(msg)
    
    return jsonify(status)

def _halt_serving(client, experiments):
    """Halt the current serving job on Floydhub.

    We expect to serve at most one job at a time. If for some reason
        more than one job is serving, this will halt the most recently
        created serving job.
    """
    for e in experiments:
        if e.mode == 'serving':   
            if not e.is_finished:
                client.stop(e.id)  
                return
    
# Argument parsing functions

def _parse_scrape_params(args):
    """Parse url for wires, thumbnail source and timeout, story batch size."""
    
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

def _parse_retrieve_params(args):
    """Parse url for days, dates, and/or themes."""
    try:
        start, end = _parse_daysback(args)
    except ValueError:
        try: 
            start, end = _parse_dates(args)
        except (ValueError, TypeError):
            raise
    kwargs = {
        'startDate': start,
        'endDate': end
    }

    filterBy = args.get('filterby')
    if filterBy:
        if filterBy in firebaseio.ALLOWED_FILTERS:
            kwargs.update({'filterBy': filterBy})
        else:
            raise ValueError('Argument filterby must be from {}'.format(
                firebaseio.ALLOWED_FILTERS))

    themes = args.getlist('themes')
    if themes:
        try:
            known_themes = requests.get(KNOWN_THEMES_URL).json()
            if not set(themes) <= set(known_themes):
                raise ValueError('One or more themes not recognized.')
        except json.decoder.JSONDecodeError as e:
            # This won't break anything, but prevents checking user input.
            print('Parsing retrieve params. Floydhub: {}'.format(repr(e)))
        
    return themes, kwargs
    
def _parse_daysback(args):
    """Parse number of days from today and convert to start/end dates."""
    daysback = args.get('daysback', type=int)
    if not daysback:
        raise ValueError
    now = datetime.datetime.now()
    end = now + datetime.timedelta(days=1)
    start = now - datetime.timedelta(days=daysback)
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

def _parse_job(args):
    """Parse url arguments for a Floydhub job number."""
    job = request.args.get('job', type=int)
    if not job:
        raise ValueError('An integer job number is required.')
    with open(FLOYD_INIT_FILE) as f:
        expt = json.load(f)
    project = expt['name']
    job_name = os.path.join(project, str(job))
    return job_name

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

def _format_retrieve_args():
    """Produce a dict explaining retrieve args for help messaging."""
    filters = firebaseio.ALLOWED_FILTERS
    scraper_args = {
        'Required argument': {
            'daysback': ('Number of days worth of records to retrieve. ' +
                         'Expect hundreds of records per day requested.')
        },
        'Required arguments (alternate form)': {
            'start': 'Begin date in form YYYY-MM-DD',
            'end': 'End date in form YYYY-MM-DD'
        },
        'Optional arguments': {
            'themes': 'One or more from the list of known themes.',
            'filterby': 'One of {}. Defaults to {}'.format(filters, filters[0])
        },
        'Known themes': KNOWN_THEMES_URL
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
