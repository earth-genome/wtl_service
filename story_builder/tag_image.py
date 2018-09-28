"""Apply Watson Vision Recognition to tag an image with keywords describing
its subject matter.

External function: get_tags
""" 

import json
import re

import watson_developer_cloud as wdc

from config import WATSON_VISION_API_KEY
from utilities.firebaseio import FB_FORBIDDEN_CHARS

AUTH = wdc.VisualRecognitionV3(
    '2016-05-20',
    api_key=WATSON_VISION_API_KEY
)

EXCLUDED_TAG_WORDS = set([
    'color'
])
    

def get_tags(img_url):
    """Apply Watson Vision Recognition to tag image with class names.

    Argument: Url pointing to image.
    
    Returns:  Dict of class names and relevance scores.
    """
    parameters = json.dumps({'url':img_url})
    try:
        response = AUTH.classify(parameters=parameters)
        classlist = response['images'][0]['classifiers'][0]['classes']
        tags = clean_tags(classlist)
        tags = filter_tags(tags)
    except:
        tags = {}
    return tags

def filter_tags(tags):
    """Remove image tags that include EXCLUDED_TAG_WORDS."""
    for excl in EXCLUDED_TAG_WORDS:
        tags = {k:v for k,v in tags.items() if excl not in k}
    return tags

def clean_tags(classlist):
    """Remove forbidden characters and simplify NLU data structure."""
    tags = {
        re.sub(FB_FORBIDDEN_CHARS, '', c['class']):c['score']
        for c in classlist
    }
    return tags
