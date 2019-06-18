"""Class to run the TensorFlow Universal Sentence Encoder to create dense
vector representations of text sentences.

Usage. On init the class requires a TensorFlow session. From within a 
context manager:

> with tf.Session() as session:
>     coder = TFSentenceEncoder(session, pad_to=6)
>     vectors = coder(sentences)

Or: 
> session = tf.Session()
> coder = TFSentenceEncoder(session, pad_to=6)
> vectors = coder(sentences)
> sesions.close()

The class also requires a large (>1GB) TensorFlow module. The module can be 
cached locally and persistently by setting environment variable 
TFHUB_CACHE_DIR. If TFHUB_CACHE_DIR remains set, on a call to
hub.Module with the MODULE_URL, the routine will check TFHUB_CACHE_DIR 
for the module before re-downloading.

The __init__ can run several tens of seconds in building the TensorFlow 
graph for the large module. However, execution of encode() is fast. 
Before re-initializing the class, it is helpful also to reset the TF default 
graph: 
> tf.reset_default_graph()


"""

import numpy as np
import tensorflow as tf
import tensorflow_hub as hub

MODULE_URL = 'https://tfhub.dev/google/universal-sentence-encoder/2'

def trim_and_pad(sentences, N):
    """Trim list of sentences or pad with '' to return N sentences."""
    trimmed = sentences[:N]
    while len(trimmed) < N:
        trimmed.append('')
    return trimmed

class TFSentenceEncoder(object):
    """Create dense vector representations of text sentences. 

    External methods:
        __call__: Compute a numerical representation of texts.
    
    Attributes:
        placeholders: placeholder for input text sentences
        graph_embeds: tensor of placeholder sentences
        session: instance of tf.Session() 
        pad_to: Integer number of sentences to trim and pad to.
        
    """
    def __init__(self, session, module_url=MODULE_URL, pad_to=None):
        encoder = hub.Module(module_url)
        self.placeholders = tf.placeholder(dtype=tf.string, shape=[None])
        self.graph_embeds = encoder(self.placeholders)
        self.session = session
        self.session.run([tf.global_variables_initializer(),
                          tf.tables_initializer()])
        self.pad_to = pad_to
        
    def encode(self, sentences):
        """Compute a numerical representation of sentences.

        Argument sentences: list of strings

        Returns: Array of floats, with first dimension of size len(sentences)
        """
        if self.pad_to:
            tokens = np.array(trim_and_pad(sentences, self.pad_to))
        else:
            tokens = np.array(sentences)
        vectors = self.session.run(
            self.graph_embeds, feed_dict={self.placeholders: tokens.flatten()})
        return vectors.reshape(*tokens.shape, vectors.shape[-1])
    


    
        
