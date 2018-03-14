"""Apply Watson Vision Recognition to tag an image with keywords describing
its subject matter.

External function: get_tags
""" 

import json

import watson_developer_cloud as wdc

from config import WATSON_VISION_API_KEY

AUTH = wdc.VisualRecognitionV3(
    '2016-05-20',
    api_key=WATSON_VISION_API_KEY
)

def get_tags(img_url):
    """Apply Watson Vision Recognition to tag image with class names.

    Argument: Url pointing to image.
    
    Returns:  Dict of class names and relevance scores.
    """
    parameters = json.dumps({'url':img_url})
    try:
        response = AUTH.classify(parameters=parameters)
        classlist = response['images'][0]['classifiers'][0]['classes']
        tags = {c['class']:c['score'] for c in classlist}
    except:
        tags = {}
    return tags
