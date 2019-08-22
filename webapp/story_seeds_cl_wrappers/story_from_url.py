"""Simple wrapper to retrieve content, classify, geolocate and cluster
entities for a story.

Writes to file a json dump of the story data.

Usage: python story_from_url.py http://story.nytimes.com
"""

import json
import sys

from story_builder import story_builder

if __name__ == '__main__':
    try:
        url = sys.argv[1]
    except IndexError:
        print('Exiting.  No url specified.')
        print('Usage: python story_from_url.py http://story.nytimes.com')
        sys.exit()
    builder = story_builder.StoryBuilder()
    story = builder(url=url)
    savename = story.idx[:30]+'.json'
    with open(savename, 'w') as f:
        json.dump({story.idx: story.record}, f, indent=4)
