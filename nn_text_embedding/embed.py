
import os
import sys

import nltk
import numpy as np
from sklearn.externals import joblib
import tensorflow as tf
import tensorflow_hub as hub
    
EMBEDDER = hub.Module('https://tfhub.dev/google/universal-sentence-encoder/2')

# WIP: truncate texts to this many sentences (~2/3 of texts are less than
# this length):
MAX_SENTENCES = 30  

def embed(texts):
    """Compute a numerical representation of texts using EMBEDDER module.

    Argument texts: list of strings

    Returns:  An array of floats, whose first dimension has size len(texts)
    """
    tokens = [trim_and_pad(nltk.sent_tokenize(text)) for text in texts]
    tokens = np.asarray(tokens)
    # WIP: replace this with a locally cached copy
    embedder = hub.Module(
        'https://tfhub.dev/google/universal-sentence-encoder/2')
    embeddings = EMBEDDER(tokens.flatten())
    with tf.Session() as session:                                         
        session.run([tf.global_variables_initializer(),
                     tf.tables_initializer()])
        vectors = session.run(embeddings)
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
    vectors = embed(data['data'])
    joblib.dump({'vectors': vectors, 'labels': data['labels']},
                data_file.split('.pkl')[0] + '-embedded.pkl')
    
    
        
