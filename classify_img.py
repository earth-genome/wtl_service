"""Wrapper to restore and run an image classifier.

Returns a probability the story associated to input url is a good candidate
for satellite imagery, based on latest stored model.
"""

import os
import sys

from sklearn.externals import joblib

from story_builder import tag_image

MODEL = 'bagofwords/NBimage_models/latest_model.pkl'

if __name__ == '__main__':
    try:
        url = sys.argv[1]
    except IndexError:
        print('Exiting.  No url specified.')
        print('Usage: python classify_img.py http://url.to.image.jpg')
        sys.exit()
    tags = tag_image.WatsonTagger().get_tags(url)
    classifier = joblib.load(MODEL)
    print('\nProbability: {:.3f}\n'.format(classifier.predict_datum(tags)))
