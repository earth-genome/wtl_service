"""Functions to preprocess and vectorize texts ahead of classification.

Defaults are tuned to news stories scraped from NewsAPI.

External functions: vectorize(), get_vocab_count()

    Usage:  vectors, vectorizer = vectorize(texts)

For diagnostics on a text corpus:

    Usage: word_counts = get_vocab_counts(*count_vectorizer(texts))

"""

import functools
import numpy as np
import re
import pkg_resources

from nltk.stem.snowball import SnowballStemmer
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

BAD_SYMBOLS = '[\d?!@#$%^&\*_\+]+'

STOP_WORD_FILES = [
    pkg_resources.resource_filename(__name__, 'news_stop_words.txt'),
    pkg_resources.resource_filename(__name__, '../newsapi_outlets.txt')
]

def strip_symbols(text, symbols=BAD_SYMBOLS):
    """Remove regex-coded symobls from text."""
    return re.sub(symbols, '', text)

def preprocessor(text, stem=False):
    """Creates a custom preprocessor for the TfidfVectorizer."""
    text = strip_symbols(text.lower())
    if stem:
         stemmer = SnowballStemmer('english')
         tokens = [stemmer.stem(word) for word in text.split()]
         text = ' '.join(tokens)
    return text

def build_stop_words(filenames):
    """Add custom list(s) to sklearn standard 'english' stop words."""
    new_words = []
    for fname in filenames:
        with open(fname) as f:
            new_words += [line.strip() for line in f]
    # remove hyphens (relevant for newsapi outlets): 
    new_words = [w for hyph in new_words for w in hyph.split('-')]
    stop_words = ENGLISH_STOP_WORDS.union(new_words)
    return stop_words

STOP_WORDS = build_stop_words(STOP_WORD_FILES)

def vectorize(texts, stop_words=STOP_WORDS):
    """Transform an input list of strings to Tf-idf vectors.

    Arguments:
        List of strings
        Stop words: None, 'english', or hard-coded STOP_WORDS
        
    Returns:
        vectors and the vectorizer, which has vocabulary_ and idf_ (weights)
        as attributes.
    """
    vectorizer = TfidfVectorizer(
        input='content',
        preprocessor = functools.partial(preprocessor, stem=False),
        stop_words = stop_words
    )
    vectors = vectorizer.fit_transform(texts)
    return vectors, vectorizer

def count_vectorize(texts, stop_words=STOP_WORDS):
    """Transform an input list of strings to vectors of word counts.

    Arguments:
        List of strings
        Stop words: None, 'english', or hard-coded STOP_WORDS
        
    Returns:
        vectors and the vectorizer, which has vocabulary_ as attribute.
    """
    vectorizer = CountVectorizer(
        input='content',
        preprocessor = functools.partial(preprocessor, stem=False),
        stop_words = stop_words
    )
    vectors = vectorizer.fit_transform(texts)
    return vectors, vectorizer

def get_vocab_counts(vectors, vectorizer):
    """Tally the occurances of tokens in vectors, given the
    vocabulary attribute of a CountVectorize instance. (Diagnostic.)
    """
    word_counts = np.sum(vectors.toarray(), axis=0)
    words = vectorizer.get_feature_names()
    return {word: count for word, count in zip(words, word_counts)}




