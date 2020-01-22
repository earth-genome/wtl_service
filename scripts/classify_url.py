"""Wrapper to restore and run the default WTL classifier on a news story."""

import sys

import _env
import story_builder

if __name__ == '__main__':
    try:
        url = sys.argv[1]
    except IndexError:
        print('Exiting.  No url specified.')
        print('Usage: python nbclassify_url.py http://story.nytimes.com')
        sys.exit()
    builder = story_builder.StoryBuilder(parse_images=True, geoloc_url=None)
    story = builder.assemble_content(url)
    builder.classify(story)
