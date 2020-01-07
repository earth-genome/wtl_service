"""Apply Watson Vision Recognition to identify objects, qualities, and themes 
in web-based images.

Class WatsonTagger, descendant of wdc.VisualRecognitionV3
    External method: get_tags

Usage: 
> tags = WatsonTagger().get_tags(img_url)

""" 

import json
import re
import os

import watson_developer_cloud as wdc

from firebaseio import FB_FORBIDDEN_CHARS

API_KEY_ENV_VAR = 'WATSON_VISION_API_KEY'

EXCLUDED_TAG_WORDS = ['color']

class WatsonTagger(wdc.VisualRecognitionV3):
    """Class to identify objects, qualities, and themes in images.

    Descendant external method:
        get_tags: Apply Watson Vision Recognition to label an image.

    """
    def __init__(self, version='2018-03-19', apikey=None):
        if not apikey:
            apikey = os.environ[API_KEY_ENV_VAR]
        super().__init__(version, iam_apikey=apikey)
    
    def get_tags(self, img_url):
        """Apply Watson Vision Recognition to label content of image.
    
        Returns:  Dict of class names and relevance scores.
        """
        try:
            result = self.classify(url=img_url).get_result()
            classlist = result['images'][0]['classifiers'][0]['classes']
        except (wdc.WatsonApiException, IndexError, KeyError) as e:
            print('Tagging image: {}'.format(repr(e)))
            classlist = []
        
        return self._clean_tags(classlist)

    def _clean_tags(self, classlist):
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
