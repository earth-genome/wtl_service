
import os
import sys

import nltk
import numpy as np
from sklearn.externals import joblib
import tensorflow as tf
import tensorflow_hub as hub

# The module can be cached locally and persistently by setting environment
# variable TFHUB_CACHE_DIR. If TFHUB_CACHE_DIR remains set, on a call to
# hub.Module with the remote MODULE_PATH, the routine will check
# TFHUB_CACHE_DIR for the module before re-downloading.
MODULE_PATH = 'https://tfhub.dev/google/universal-sentence-encoder/2'

# WIP: truncate texts to this many sentences (~2/3 of texts are less than
# this length):
MAX_SENTENCES = 30


class SentenceEncoder(object):
    """Create high-dimensional vector representations of text sentences. 

    Methods:
        __call__: Compute a numerical representation of texts.
    
    Attributes:
        graph_embeds: tf.Tensor of (embedded) placeholder sentences.
        session: A tf.Session instance.  Must be closed manually to liberate
            memory by calling session.close()
    """
    def __init__(self, module_path=MODULE_PATH):

        encoder = hub.Module(module_path)
        self.sentences = tf.placeholder(dtype=tf.string, shape=[None])
        self.graph_embeds = encoder(self.sentences)
        self.session = tf.Session()
        self.session.run([tf.global_variables_initializer(),
                          tf.tables_initializer()])
        
    def __call__(self, texts):
        """Compute a numerical representation of texts.

        Argument texts: list of strings

        Returns:  An array of floats, whose first dimension has size len(texts)
        """
        tokens = [trim_and_pad(nltk.sent_tokenize(text)) for text in texts]
        tokens = np.asarray(tokens)
        vectors = self.session.run(
            self.graph_embeds, feed_dict={self.sentences: tokens.flatten()})
        return vectors.reshape(*tokens.shape, vectors.shape[-1])
    
def trim_and_pad(sentences, max_len=MAX_SENTENCES):
    """Return a list of sentences of max_len, padding with empty strings if
    necessary.
    """
    sentences = sentences[:max_len]
    while len(sentences) < max_len:
        sentences.append('')
    return sentences

if __name__ == '__main__':
    try:
        data_file = sys.argv[1]
        data = joblib.load(data_file)
    except Exception as e:
        sys.exit('{}\n\nUsage: python embed.py stored_data.pkl.'.format(
            repr(e)))
    coder = SentenceEncoder()
    vectors = coder(data['data'])
    coder.session.close()
    joblib.dump({'vectors': vectors, 'labels': data['labels']},
                data_file.split('.pkl')[0] + '-embedded.pkl')
    
    
        
