"""Wrapper to restore and run a naivebayes.LogisticStacker() model.

Returns a probability the story associated to input url is a good candidate
for satellite imagery, based on latest stored model.
"""

import sys

from sklearn.externals import joblib

import extract_text
import firebaseio

CLASSIFIER = joblib.load('naivebayes/Stacker_models/latest_model.pkl')

if __name__ == '__main__':
    try:
        url = sys.argv[1]
    except IndexError:
        print('Exiting.  No url specified.')
        print('Usage: python nbclassify_url.py http://story.nytimes.com')
        sys.exit()
    record = {'url': url}
    record.update(extract_text.get_parsed_text(url))
    story = firebaseio.DBItem('/null', None, record)
    print('\nProbability: {:.2f}\n'.format(CLASSIFIER([story])[0]))
