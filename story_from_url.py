"""Simple wrapper to retrieve content, classify, geolocate and cluster
entities for a story.

Writes to file a json dump of the story data.

Usage: python story_from_url.py http://story.nytimes.com
"""

import json
import sys

from story_builder.story_builder import StoryBuilder

if __name__ == '__main__':
    try:
        url = sys.argv[1]
    except IndexError:
        print('Exiting.  No url specified.')
        print('Usage: python story_from_url.py http://story.nytimes.com')
        sys.exit()
    builder = StoryBuilder(parse_images=True)
    story, clf, feed = builder(url=url)
    savename = story.idx[:30]+'.json'
    with open(savename, 'w') as f:
        json.dump(json.loads(feed), f, indent=4)
