"""Routines to request thumbnails from the earthrise-imagery web app.

Class RequestThumbnails.

The __call__ method must be used within an aysncio event loop
and be provided an active instance of aiohttp.ClientSession(). Usage with
defaults:

> loop = asyncio.get_event_loop()
> loop.run_until_complete(main(lat, lon))

"""

import aiohttp
import asyncio
import json

import numpy as np

THUMBNAIL_PARAMS = {
    'N': str(4),
    'skip': str(90),
    'thumbnails': 'true',
}
PROVIDER_PARAMS = {
    'planet': {
        'item_types': 'PSScene3Band',
        'asset_types': 'analytic',
        'write_styles': 'contrast',
        'clouds': str(5),
        'min_intersect': str(1.0),
        'bucket_name': 'planet-thumbnails',
        'scale': str(3.0),
        'waittime': 5
    },
    'landsat': {
        'write_styles': 'landsat_contrast',
        'bucket_name': 'landsat-thumbnails',
        'scale': str(20.0),
        'waittime': 1
    }
}
 

## Uncomment to run on localhost
# import os
# os.environ['NO_PROXY'] = '127.0.0.1'
## Then use in request_thumbnails: app_url='http://127.0.0.1:5000/pull'

class RequestThumbnails(object):
    """Class to request thumbnails from the earthrise-imagery web app.

    Attributes:
        provider: name of satellite imagery provider
        base_payload: parameters defining the web app request
        waittime: integer seconds to sleep before checking return from app
        app_url: web app endpoint

    Method: __call__: Request image thumbnails.
    """
    
    def __init__(self, provider,
                 thumbnail_params=THUMBNAIL_PARAMS,
                 provider_params=PROVIDER_PARAMS,
                 app_url='http://earthrise-imagery.herokuapp.com/pull'):
                 
        self.provider = provider
        self.base_payload = dict(provider=provider, **THUMBNAIL_PARAMS)
        self.base_payload.update(PROVIDER_PARAMS[provider])
        self.waittime = self.base_payload.pop('waittime')
        self.app_url = app_url

    async def __call__(self, session, lat, lon):
        """Request image thumbnails from a web app.

        Arguments:
            session: an instance of aiohttp.ClientSession()
            lat, lon: decimal latitude and longitude

        Returns: list of urls to cloud-stored thumbnails 
        """
        print('Requesting thumbnails\n')
        payload = dict(lat=str(lat), lon=str(lon), **self.base_payload)
        async with session.get(self.app_url, params=payload) as response:
            pull_summary = await response.json(content_type=None)

        report = 'In progress.'
        while report == 'In progress.':
            await asyncio.sleep(self.waittime)
            async with session.get(pull_summary['Links']) as links_resp:
                report = await links_resp.json(content_type=None)

        if 'Exception' in [k for r in report for k in r.keys()]:
            raise Exception(json.dumps(report))
        else:
            thumbnail_urls = [u for r in report for u in r['urls']]

        return thumbnail_urls

# Session handling wrapper. To call within an asyncio event loop.
async def main(provider, lat, lon):
    requester = RequestThumbnails(provider)
    async with aiohttp.ClientSession() as session:
        thumbnail_urls = await requester(session, lat, lon)
    return thumbnail_urls
