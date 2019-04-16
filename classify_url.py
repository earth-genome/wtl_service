"""Wrapper to restore and run a classifier on a news story.

Returns a probability the story (possibly text and image) associated to
input url is a good candidate for satellite imagery, based on latest
stored model.
"""

import sys

from sklearn.externals import joblib

from story_builder import story_builder

MODEL = 'bagofwords/Stacker_models/latest_model.pkl'

if __name__ == '__main__':
    try:
        url = sys.argv[1]
    except IndexError:
        print('Exiting.  No url specified.')
        print('Usage: python nbclassify_url.py http://story.nytimes.com')
        sys.exit()
    builder = story_builder.StoryBuilder(parse_images=True, model=None, 
                                         geolocating=False)
    story = builder.assemble_content(url)
    classifier = joblib.load(MODEL)
    print('\nProbability: {:.3f}\n'.format(classifier.predict_story(story)))
