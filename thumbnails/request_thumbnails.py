"""Routines to request thumbnails from the earthrise-imagery web app.

The function request_thumbnails must be used within an aysncio event loop
and be provided an active instance of aiohttp.ClientSession(). Usage with
defaults:

> loop = asyncio.get_event_loop()
> loop.run_until_complete(main(lat, lon))

"""

import aiohttp
import asyncio
import datetime

import numpy as np

PLANET_PARAMS = {
    'provider': 'planet',
    'asset_types': 'analytic',
    'write_styles': 'contrast',
    'clouds': str(5),
    'thumbnails': 'true',
    'bucket_name': 'planet-thumbnails',
    'scale': str(5.0)
}

WAITTIME = 5

async def request_thumbnails(
    session,
    lat, lon,
    num_steps=4,
    days_gap=90,
    base_url='http://earthrise-imagery.herokuapp.com/pull',
    base_payload=PLANET_PARAMS):
    """Request a time-gapped series of image thumbnails from a web app.

    Arguments:
        session: an instance of aiohttp.ClientSession()
        lat, lon: latitude and longitude
        num_steps: number of time steps
        days_gap: days between steps
        base_url: web app endpoint
        base_payload: parameters defining the web app request
    
    Returns: list of urls to cloud-stored thumbnails 
    """
    common_payload = dict({'lat': str(lat), 'lon': str(lon)}, **base_payload)
    enddates = [datetime.date.today() - datetime.timedelta(days=int(gap))
                for gap in np.arange(num_steps)*days_gap]
    startdates = [enddate - datetime.timedelta(days=days_gap)
                  for enddate in enddates]

    payloads = []
    for (end, start) in zip(enddates, startdates):
        payloads.append(
            dict({
                'end': str(end.isoformat()),
                'start': str(start.isoformat())
            },
            **common_payload))

    async def fetch(session, base_url, payload):
        async with session.get(base_url, params=payload) as response:
            pull_summary = await response.json(content_type=None)
    
        report = 'In progress.'
        while report == 'In progress.':
            await asyncio.sleep(WAITTIME)
            async with session.get(pull_summary['Links']) as links_resp:
                report = await links_resp.json(content_type=None)

        urls = [u for r in report for u in r['urls']]
        return urls

    fetch_tasks = [fetch(session, base_url, payload) for payload in payloads]
    results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

    thumbnail_urls = []
    for url_list in results:
        if type(url_list) is list:
            thumbnail_urls += url_list
        
    return thumbnail_urls

# Session handling wrapper. To call within an asyncio event loop.
async def main(lat, lon):
    async with aiohttp.ClientSession() as session:
        thumbnail_urls = await request_thumbnails(session, lat, lon)
        return thumbnail_urls
