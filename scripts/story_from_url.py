"""Simple wrapper to retrieve content, classify, and geolocate a story.

Writes to file a json dump of the story data.

Usage: python story_from_url.py http://story.nytimes.com
"""

import json
import sys

import _env
import story_builder

if __name__ == '__main__':
    try:
        url = sys.argv[1]
    except IndexError:
        print('Exiting.  No url specified.')
        print('Usage: python story_from_url.py http://story.nytimes.com')
        sys.exit()
    builder = story_builder.StoryBuilder(reject_for_class=False, weather_cut=0)
    story = builder(url)
    savename = story.idx[:30]+'.json'
    with open(savename, 'w') as f:
        json.dump({story.idx: story.record}, f, indent=4)
