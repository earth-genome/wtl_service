"""Functions to vectorize images ahead of classification.

Image tags and relevance scores (extracted via module story_builder/tag_image)
are used to build a vocabulary and corresponding vectors. Vectorizing
opterations are modeled after those in sklearn.feature_extraction.text
(ref. prep_text.py) for seamless integration in sklearn classifiers
(ref. naivebayes.py).

External function:
    build_vectorizer: Creates vectors and a vectorizer from a tagslist, a
        a list of dicts of form {tag1: score1, tag2: score2, ...}

External class:
    ImageVectorizer:
        Attribute: vocabulary_
        Method:  transform (tagslist into vectors)
"""
 
import numpy as np
import sys

class ImageVectorizer(object):
    """Vectorize images.

    Attribute: vocabulary_
    Methods:
        transform (list of dicts of tags and relevance scores into vectors)
    """
    def __init__(self, vocabulary):
        self.vocabulary_ = vocabulary

    def transform(self, tagslist):
        """Transform image tags into vectors.

        Argument:  tagslist: list of dicts of tags and relevance scores
            for each image

        Returns:  Numpy array
        """
        vectors = np.zeros((len(tagslist), len(self.vocabulary_)))
        for n, tags in enumerate(tagslist): 
            for word, score in tags.items():
                try: 
                    vectors[n, self.vocabulary_[word]] = score
                except KeyError:
                    pass
        return vectors
        
def build_vectorizer(tagslist):
    """Create vectors and a vectorizer from a list of tag dicts."""
    vocab = build_vocabulary(tagslist)
    vectorizer = ImageVectorizer(vocab)
    vectors = vectorizer.transform(tagslist)
    return vectors, vectorizer

def build_vocabulary(tagslist):
    """Extract set of all tags from training images."""
    all_instances = [t for tags in tagslist for t in tags.keys()]
    vocabset = set(all_instances)
    vocab = {word:index for index, word in enumerate(vocabset)}
    return vocab


