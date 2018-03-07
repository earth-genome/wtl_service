"""Wrapper for naivebayes.NBTextClassifier.predict_url.

Returns a probability the story associated to input url is a good candidate
for satellite imagery, based on latest stored model.
"""

import sys

from naivebayes import naivebayes

if __name__ == '__main__':
    try:
        url = sys.argv[1]
    except IndexError:
        print('Exiting.  No url specified.')
        print('Usage: python nbclassify_url.py http://story.nytimes.com')
        sys.exit()
    nbc = naivebayes.NBTextClassifier()
    print('\nProbability: {:.2f}\n'.format(nbc.predict_url(url)))
