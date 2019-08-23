"""A Flask web app to source stories for the Where to Look (WTL) database.

Story retrieval is handled by web app directly; story build and classification
is pushed to a Redis queue and handled by the worker process in worker.py.
"""

import datetime
from inspect import getsourcefile
from json.decoder import JSONDecodeError
import os
import traceback
import urllib.parse
import sys

from flask import Flask, json, jsonify, request
from flask_restful import inputs
import numpy as np
import requests
from rq import Queue
import shapely

from harvest_urls import WIRE_URLS
import news_scraper
from request_thumbnails import PROVIDER_PARAMS
from story_builder.story_builder import FLOYD_URL
from utilities import firebaseio, log_utilities
from utilities.firebaseio import ALLOWED_ORDERINGS
from utilities.geobox import us_counties
import worker

app_dir = os.path.dirname(os.path.abspath(getsourcefile(lambda:0)))
models_dir = os.path.join(os.path.dirname(app_dir), 'saved_models')
sys.path.append(models_dir)
from geoloc_model import restore

# App
q = Queue('default', connection=worker.connection, default_timeout=86400)
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Logging
fh = log_utilities.get_rotating_handler(
    os.path.join(app_dir, 'logs/app.log'), when='D', interval=7, backupCount=3)
app.logger.addHandler(fh)

# Learned models to serve
locations_net, locations_graph = restore.restore()
print(locations_net.estimator.summary())

KNOWN_THEMES_URL = os.path.join(FLOYD_URL, 'known_themes')
with open('training_themes.txt') as f:
    TRAINING_THEMES = [l.strip() for l in f.readlines()]

US_CSV = os.path.join(os.path.dirname(__file__), 'us_county_geojson.csv')
US_GEOJSON = os.path.join(os.path.dirname(__file__), 'us_allstates.json')
EVP_GEOJSON = os.path.join(os.path.dirname(__file__), 'us_evpstates.json')

BOUNDARY_TOL = .2

DATABASE = 'story-seeds'
DB_CATEGORY = '/WTL'
TRAINING_DB = 'good-locations'
TRAINING_DB_CATEGORY = '/labeled_themes'

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
        'Get a geojson for US states or counties.':
            ''.join((request.url, 'us-geojsons?')),
        'Determine relevance of a geolocation':
            ''.join((request.url, 'locations'))
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

    kwargs.update({'served_models_url': request.url_root})
    job = q.enqueue_call(
        func=news_scraper.scraper_wrapper, args=(wires,), kwargs=kwargs)

    return jsonify(_format_scraping_guide())

@app.route('/locations', methods=['GET', 'POST'])
def classify_locations():
    msg = _locations_help(request.url)
    if request.method == 'GET':
        return jsonify(msg), 405

    try:
        locations_data = json.loads(request.form['locations_data'])
        with locations_graph.as_default():
            predictions = locations_net.predict_relevance(locations_data)
    except:
        tb = traceback.format_exc()
        app.logger.error('Classifying locations: {}'.format(tb))
        return jsonify(tb), 400

    # convert from np.float32 to float32 for JSON-serializeable output
    predictions = [{k:float(v) for k,v in p.items()} for p in predictions]
    return jsonify(predictions)
    
@app.route('/retrieve')
def retrieve():
    """Retrieve records from the WTL database."""
    msg = _help_msg(
        request.base_url,
        ('daysback=3&filterby=scrape_date&themes=water&themes=conflict'
         '&states=CA&counties=Yolo&counties=Napa'),
        _format_retrieve_args())

    try:
        themes, kwargs = _parse_retrieve_params(request.args)
        footprint = _get_counties(request.args)
    except (ValueError, TypeError) as e:
        msg['Exception'] = repr(e)
        return jsonify(msg)

    stories = firebaseio.DB(DATABASE).grab_stories(DB_CATEGORY, **kwargs)
    
    if themes:
        stories = [s for s in stories
                   if set(themes).intersection(s.record.get('themes', {}))]
            
    if footprint:
        footprint = footprint.simplify(BOUNDARY_TOL, preserve_topology=False)
        filtered = []
        for s in stories:
            try:
                loc = s.record['core_location']
            except KeyError:
                try:
                    # For pre-Feb. 2019 story formatting:
                    loc = s.record['clusters'][0]['centroid']
                except:
                    continue
            lonlat = shapely.geometry.Point(loc['lon'], loc['lat'])
            if lonlat.within(footprint):
                filtered.append(s)
        stories = filtered.copy()

    return jsonify([_clean(s) for s in stories])

@app.route('/retrieve-story')
def retrieve_story():
    """Retrieve a story index and record from the WTL database."""
    msg = _help_msg(request.base_url,
                    'idx=Index of the story in the database', '')
    try:
        story = _retrieve_story(request.args)
    except ValueError as e:
        msg['Exception'] = repr(e)
        return jsonify(msg)

    return jsonify({story.idx: story.record})

def _retrieve_story(args):
    """Working routine to retrieve a story, with unified error messaging.

    Raises: ValueError if story index is not given or malformed, or if no
        story with that index is found.

    Returns: A DBItem story.
    """
    idx = _parse_index(args)
    try:
        record = firebaseio.DB(DATABASE).get(DB_CATEGORY, idx)
    except JSONDecodeError as e:
        raise ValueError(('Malformed story index: <{}> '.format(idx) + 
                         'Ref. firebaseio.py for list of forbidden chars.'))
    if not record:
        raise ValueError('No story found with index: <{}>'.format(idx))
    return firebaseio.DBItem('/null', idx, record)
   
def _clean(story):
    """Curate story data for web presentation."""
    title = story.record.get('title', '')
    themes = story.record.get('themes', {})
    loc = story.record.get('core_location', {})

    rec = {
        'Title': title,
        'Source url': story.record.get('url'),
        'Location': loc.get('text', ''),
        'Latlon': [loc.get('lat'), loc.get('lon')] if loc else [],
        'Themes': themes,
        'Full record': request.url_root + 'retrieve-story?idx={}'.format(
            urllib.parse.quote(story.idx))
    }
    return rec

@app.route('/label')
def label():
    """Add theme labels to a story in WTL and post to good-locations."""
    msg = _help_msg(
        request.base_url,
        'themes=pollution&themes=water&idx=Index of the story in the database',
        {'known themes': TRAINING_THEMES})

    try:
        themes = request.args.getlist('themes')
        if not set(themes) <= set(TRAINING_THEMES):
            raise ValueError('One or more themes not recognized.')
        story = _retrieve_story(request.args)
    except ValueError as e:
        msg['Exception'] = repr(e)
        return jsonify(msg)

    story.category = TRAINING_DB_CATEGORY
    story.record.update({'labeled_themes': themes})
    rec_uploaded = firebaseio.DB(TRAINING_DB).put_item(story, verbose=True)

    if rec_uploaded:
        return jsonify({
            'Successfully posted to {}'.format(TRAINING_DB): story.idx,
            'With labeled themes': rec_uploaded.get('labeled_themes')
        })
    else:
        return jsonify({'Failed to upload': story.idx})

@app.route('/us-geojsons')
def us_geojsons():
    """Get geojsons for U.S. states or counties."""
    msg = _help_msg(request.base_url,
                    'states=CA&counties=Yolo&counties=Napa',
                    _format_counties_args())
    try:
        footprint = _get_counties(request.args)
        if not footprint:
            raise ValueError('At least one state is required.')
    except (ValueError, TypeError) as e:
        msg['Exception'] = repr(e)
        return jsonify(msg)

    return jsonify(shapely.geometry.mapping(footprint))


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
    
    if not wires or not set(wires) <= set(WIRE_URLS):
        raise ValueError('Supported wire are {}'.format(set(WIRE_URLS)))
    
    tns = kwargs['thumbnail_source']
    if tns and tns not in PROVIDER_PARAMS:
        raise ValueError('thumbnail_source must be from {}'.format(
            set(PROVIDER_PARAMS)))

    kwargs = {k:v for k,v in kwargs.items() if v is not None}
    return wires, kwargs

def _parse_retrieve_params(args):
    """Parse url for days, dates, and/or themes."""
    try:
        start, end = _parse_daysback(args)
    except ValueError:
        try: 
            start, end = _parse_dates(args)
        except ValueError:
            raise
    kwargs = {
        'startAt': start,
        'endAt': end
    }

    filterby = args.get('filterby', default=next(iter(ALLOWED_ORDERINGS)))
    if filterby not in ALLOWED_ORDERINGS:
        raise ValueError('Supported filterby options are {}'.format(
            ALLOWED_ORDERINGS))
    kwargs.update({'orderBy': filterby})

    themes = _parse_themes(args)
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
    try: 
        start = datetime.datetime.strptime(start, '%Y-%m-%d').date()
        end = datetime.datetime.strptime(end, '%Y-%m-%d').date()
    except TypeError:
        raise ValueError('Either daysback or both start and end are required.')
    
    return start.isoformat(), end.isoformat()

def _parse_themes(args):
    """Parse url for themes."""
    themes = args.getlist('themes')
    if themes:
        try:
            known_themes = requests.get(KNOWN_THEMES_URL).json()
            if not set(themes) <= set(known_themes):
                raise ValueError('One or more themes not recognized.')
        except JSONDecodeError as e:
            # This won't break anything, but prevents checking user input.
            print('Parsing themes. Floydhub: {}'.format(repr(e)))
    return themes

def _get_counties(args):
    """Parse url args for states and counties. 

    Returns: A shapely geometric object 
    """
    states = args.getlist('states')
    states = [s.upper() for s in states]
    counties = args.getlist('counties')
    if not states and not counties:
        return

    if 'ALL' in states:
        with open(US_GEOJSON) as f:
            footprint = shapely.geometry.asShape(json.load(f))
    elif 'EVP' in states:
         with open(EVP_GEOJSON) as f:
            footprint = shapely.geometry.asShape(json.load(f))
    elif states and not counties:
        cb = us_counties.CountyBoundaries(csv=US_CSV)
        footprint = cb.combine_states(states)
    elif counties and len(states) != 1:
        raise ValueError('A single state must be specified with counties.')
    else:
        cb = us_counties.CountyBoundaries(csv=US_CSV)
        footprint = cb.combine_counties(counties, next(iter(states)))
    return footprint

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
        'notes': notes
    }
    return msg

def _format_scraper_args():
    """Produce a dict explaining scraper args for help messaging."""
    scraper_args = {
        'Argument': {
            'wires': 'One or more of {}'.format(set(WIRE_URLS))
        },
        'Optional arguments': {
            'thumbnail_source': 'One of {}'.format(set(PROVIDER_PARAMS)),
            'thumbnail_timeout': 'Integer number of seconds',
            'batch_size': ('Integer number of records to gather for ' +
                'asynchronous processing.'),
            'parse_images': ('True/False whether to include images from ' +
                             'news stories in their classification.') 
        }
    }
    return scraper_args

def _locations_help(url):
    msg = {
        'Method': 'POST a JSON-serialized list of locations data.',
        'Example': ("requests.post('{}', ".format(url) +
                    "data = {'locations_data':json.dumps(<list of dicts>)})")
    }
    return msg

def _format_retrieve_args():
    """Produce a dict explaining retrieve args for help messaging."""
    filters = ALLOWED_ORDERINGS
    scraper_args = {
        'Argument': {
            'daysback': ('Number of days worth of records to retrieve. ' +
                         'Expect hundreds of records per day requested.')
        },
        'Arguments (alternate form)': {
            'start': 'Begin date in form YYYY-MM-DD',
            'end': 'End date in form YYYY-MM-DD'
        },
        'Optional arguments': {
            'themes': 'One or more from the list of known themes.',
            'filterby': 'One of {}. Defaults to {}'.format(
                filters, next(iter(filters)))
        },
        'known themes': KNOWN_THEMES_URL
    }
    scraper_args.update({
        'states and counties': request.url_root + 'us-geojsons'
    })
    return scraper_args

def _format_counties_args():
    """Produce a dict explaining counties args for help messaging."""
    cb = us_counties.CountyBoundaries(csv=US_CSV)
    counties_args = {
        'Argument': {
            'states': 'One or more U.S. state postal codes, or EVP, or ALL'
        },
        'Optional argument': {
            'counties': 'One or more U.S. county names. Requires also a state.'
        },
        'US states': cb.get_statenames(),
        'US states with counties': cb.get_countynames()
    }
    return counties_args

def _format_scraping_guide():
    """Produce a message to return when scrape is called."""
    guide = {
        'Scraping': 'Now. Records will be continuously posted to WTL.',
        'Retrieve records': '{}'.format(request.url_root + 'retrieve')
    }
    return guide

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0')
