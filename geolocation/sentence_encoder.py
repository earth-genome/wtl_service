"""Class to run the TensorFlow Universal Sentence Encoder to create dense
vector representations of text sentences.

Usage. On init the class requires a TensorFlow session, e.g. from within a 
context manager:

with tf.Session() as sess:
    coder = TFSentenceEncoder(sess)
    vectors = coder(sentences)

The class also requires a large (>1GB) TensorFlow module. The module can be 
cached locally and persistently by setting environment variable 
TFHUB_CACHE_DIR. If TFHUB_CACHE_DIR remains set, on a call to
hub.Module with the MODULE_URL, the routine will check
TFHUB_CACHE_DIR for the module before re-downloading.
"""

import numpy as np
import tensorflow as tf
import tensorflow_hub as hub

from geolocation.geolocate import MAX_MENTIONS

MODULE_URL = 'https://tfhub.dev/google/universal-sentence-encoder/2'

def trim_and_pad(sentences, N):
    """Trim list of sentences or pad with '' to return N sentences."""
    trimmed = sentences[:N]
    while len(trimmed) < N:
        trimmed.append('')
    return trimmed

class TFSentenceEncoder(object):
    """Create high-dimensional vector representations of text sentences. 

    External methods:
        __call__: Compute a numerical representation of texts.
    
    Attributes:
        placeholders: placeholder for input text sentences
        graph_embeds: tensor of placeholder sentences
        session: TensorFlow session 
        
    """
    def __init__(self, session, module_url=MODULE_URL):
        encoder = hub.Module(module_url)
        self.placeholders = tf.placeholder(dtype=tf.string, shape=[None])
        self.graph_embeds = encoder(self.placeholders)
        self.session = session
        self.session.run([tf.global_variables_initializer(),
                          tf.tables_initializer()])
        
    def encode(self, mentions, pad_to=MAX_MENTIONS):
        """Compute a numerical representation of texts.

        Arguments:
            mentions: list of strings
            pad_to: If not None, trim and pad mentions to this number of 
                strings.

        Returns: Array of floats, with first dimension of size len(mentions)
        """
        if pad_to:
            mentions = trim_and_pad(mentions, pad_to)
            #tokens = np.array(trim_and_pad(mentions, pad_to))
        #else:
        #    tokens = np.array(mentions)
        tokens = np.array(' '.join(mentions))
        vectors = self.session.run(
            self.graph_embeds, feed_dict={self.placeholders: tokens.flatten()})
        return vectors.reshape(*tokens.shape, vectors.shape[-1])
    


    
        
