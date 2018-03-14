"""Apply Watson Vision Recognition to tag images with keywords describing
their subject matter.

External function: get_tags
""" 

import json

import watson_developer_cloud as wdc

from config import WATSON_VISION_API_KEY

AUTH = wdc.VisualRecognitionV3(
    '2016-05-20',
    api_key=WATSON_VISION_API_KEY
)

def get_tags(img_urls):
    """Apply Watson Vision Recognition to tag images with class names.

    Argument: List of urls.
    
    Returns:  List of dicts composed of class names and relevance scores.
    """
    tagslist = []
    for url in img_urls:
        parameters = json.dumps({'url':url})
        try:
            response = AUTH.classify(parameters=parameters)
            classlist = response['images'][0]['classifiers'][0]['classes']
            cleaned = {}
            for c in classlist:
                cleaned.update({c['class']: c['score']})
            tagslist.append(cleaned)
        except:
            tagslist.append({})
    return tagslist
