# TODO: import routines from news-scrape/webapp/scraper/main.py

import story

# for passing kwargs to story.new_story(), default is to only pass
# those which fall in STORY_METADATA.  (otherwise much unneeded
# metadata from newsapi articles will be stored.)

# kwargs = {k:v for k,v in article.iteritems() if k in STORY_METADATA}

STORY_METADATA = [
    'title',
    'date',
    'outlet',
    'description',
    'url'
    ]
