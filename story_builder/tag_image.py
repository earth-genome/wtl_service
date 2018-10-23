"""Apply Watson Vision Recognition to tag an image with keywords describing
its subject matter.

External function: get_tags
""" 

import json
import re

import watson_developer_cloud as wdc

from config import WATSON_VISION_API_KEY
from utilities.firebaseio import FB_FORBIDDEN_CHARS

SERVICE = wdc.VisualRecognitionV3(
    '2018-03-19',
    iam_apikey=WATSON_VISION_API_KEY)

EXCLUDED_TAG_WORDS = ['color']

def get_tags(img_url):
    """Apply Watson Vision Recognition to tag image with class names.

    Argument: Url pointing to image.
    
    Returns:  Dict of class names and relevance scores.
    """
    try:
        result = SERVICE.classify(url=img_url).get_result()
        classlist = result['images'][0]['classifiers'][0]['classes']
    except (wdc.WatsonApiException, IndexError, KeyError) as e:
        print('Tagging image: {}'.format(repr(e)))
        classlist = []
        
    return clean_tags(classlist)

def clean_tags(classlist):
    """Clean classlist to various specs.

    The function removes Firebase forbidden characters, simplifies the
        data structure, and filters against EXCLUDED_TAG_WORDS.

    Argument classlist: list of dicts with keys 'class' and 'score'

    Returns: dict
    """
    tags = {
        re.sub(FB_FORBIDDEN_CHARS, '', c['class']):c['score']
        for c in classlist
    }
    for excl in EXCLUDED_TAG_WORDS:
        tags = {k:v for k,v in tags.items() if excl not in k}
    return tags
