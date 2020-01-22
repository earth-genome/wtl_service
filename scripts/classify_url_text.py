"""Wrapper to restore and run the default WTL text model on a news story."""

import sys

import _env
import story_builder

if __name__ == '__main__':
    try:
        url = sys.argv[1]
    except IndexError:
        print('Exiting.  No url specified.')
        print('Usage: python classify_url_text.py http://story.nytimes.com')
        sys.exit()
    builder = story_builder.StoryBuilder(parse_images=False, geoloc_url=None)
    story = builder.assemble_content(url)
    builder.classify(story)
