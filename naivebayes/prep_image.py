
import json
import numpy as np
import sys

import watson_developer_cloud as wdc

sys.path.append('../')
from config import WATSON_VISION_API_KEY

AUTH = wdc.VisualRecognitionV3(
    '2016-05-20',
    api_key=WATSON_VISION_API_KEY
)

class ImageVectorizer(object):

    def __init__(self, vocabulary):
        self.vocabulary_ = vocabulary

    def transform(self, img_urls, tagslist=None):
        """Transform img_urls into vectors scored by Visual Recognition.

        Arguments:
            img_urls: list of urls
            tagslist: list of dicts of tags for each url,
                of form {tag1: score1, tag2: score2}

        Returns:
            Numpy array
        """
        if tagslist is None:
            tagslist = tag_images(img_urls)
        vectors = np.zeros((len(img_urls), len(self.vocabulary_)))
        for n, tags in enumerate(tagslist): 
            for word, score in tags.items():
                vectors[n, self.vocabulary_[word]] = score
        return vectors

def vectorize(img_urls):
    tagslist = tag_images(img_urls)
    vocab = build_vocabulary(tagslist)
    vectorizer = ImageVectorizer(vocab)
    vectors = vectorizer.transform(img_urls, tagslist=tagslist)
    return vectors, vectorizer

def build_vocabulary(tagslist):
    """Extract set of all tags from training images."""
    all_instances = [t for tags in tagslist for t in tags.keys()]
    vocabset = set(all_instances)
    vocab = {word:index for index, word in enumerate(vocabset)}
    return vocab

def tag_images(img_urls):
    """Apply Watson Vision Recognition to tag images with class names.

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
