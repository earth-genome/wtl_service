"""Wrapper to restore and run a text classifier.

Returns a probability the story text associated to input url is a good
candidate for satellite imagery, based on latest stored model.
"""

import sys

from sklearn.externals import joblib

from story_builder import extract_text

CLASSIFIER = joblib.load('naivebayes/NBtext_models/latest_model.pkl')

if __name__ == '__main__':
    try:
        url = sys.argv[1]
    except IndexError:
        print('Exiting.  No url specified.')
        print('Usage: python classify_url_text.py http://story.nytimes.com')
        sys.exit()
    text = extract_text.get_text(url)[0]
    print('\nProbability: {:.3f}\n'.format(CLASSIFIER([text])[0]))
