"""Routines to request thumbnails from the earthrise-imagery web app.

The function request_thumbnails must be used within an aysncio event loop
and be provided an active instance of aiohttp.ClientSession(). Usage with
defaults:

> loop = asyncio.get_event_loop()
> loop.run_until_complete(main(lat, lon))

"""

import aiohttp
import asyncio
import json

import numpy as np

PLANET_PARAMS = {
    'provider': 'planet',
    'item_types': 'PSScene3Band',
    'asset_types': 'analytic',
    'write_styles': 'contrast',
    'clouds': str(5),
    'min_intersect': str(1.0),
    'N': str(4),
    'skip': str(90),
    'thumbnails': 'true',
    'bucket_name': 'planet-thumbnails',
    'scale': str(3.0)
}

WAITTIME = 5

## Uncomment to run on localhost
# import os
# os.environ['NO_PROXY'] = '127.0.0.1'
## Then use in request_thumbnails: base_url='http://127.0.0.1:5000/pull'

async def request_thumbnails(
    session,
    lat, lon,
    base_url='http://earthrise-imagery.herokuapp.com/pull',
    base_payload=PLANET_PARAMS):
    """Request image thumbnails from a web app.

    Arguments:
        session: an instance of aiohttp.ClientSession()
        lat, lon: latitude and longitude
        base_url: web app endpoint
        base_payload: parameters defining the web app request
    
    Returns: list of urls to cloud-stored thumbnails 
    """
    payload = dict({'lat': str(lat), 'lon': str(lon),}, **base_payload)
    print('Requesting thumbnails\n')

    async with session.get(base_url, params=payload) as response:
        pull_summary = await response.json(content_type=None)

    report = 'In progress.'
    while report == 'In progress.':
        await asyncio.sleep(WAITTIME)
        async with session.get(pull_summary['Links']) as links_resp:
            report = await links_resp.json(content_type=None)

    if 'Exception' in [k for r in report for k in r.keys()]:
        raise Exception(json.dumps(report))
    else:
        thumbnail_urls = [u for r in report for u in r['urls']]

    return thumbnail_urls

# Session handling wrapper. To call within an asyncio event loop.
async def main(lat, lon):
    async with aiohttp.ClientSession() as session:
        thumbnail_urls = await request_thumbnails(session, lat, lon)
        return thumbnail_urls
