"""Wrapper to restore and run the default WTL image classifier."""

import sys

import _env
import story_builder

MODEL = '../webapp/bagofwords/Stacker_models/latest_model.pkl'

if __name__ == '__main__':
    try:
        url = sys.argv[1]
    except IndexError:
        print('Exiting.  No url specified.')
        print('Usage: python classify_img.py http://url.to.image.jpg')
        sys.exit()
    builder = story_builder.StoryBuilder(parse_images=True, geoloc_url=None)
    tags = builder.image_tagger.get_tags(url)
    classifier = builder.main_model.input_classifiers[1]
    print('\nProbability: {:.3f}\n'.format(classifier.predict_datum(tags)))
