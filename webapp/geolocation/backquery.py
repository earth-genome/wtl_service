"""Select geocoded location data by matching against a text.

External class: BackQuery
Usage with defaults:
> qualified = BackQuery()(locations, text)

Typically, locations will be an output of geocode.CageCode.

"""

from inspect import getsourcefile
import os

import numpy as np

from bagofwords import prep_text

base_dir = os.path.dirname(os.path.dirname(
    os.path.abspath(getsourcefile(lambda:0))))
with open(os.path.join(base_dir, 'bagofwords/WTLtrainingtexts.txt')) as f:
    TEXT_CORPUS = [l.strip() for l in f]

EXCLUDED_ADDRESS_COMPONENTS = ['ISO_3166-1_alpha-2', 'ISO_3166-1_alpha-3',
    '_type', 'country_code', 'road_type', 'postcode']

class BackQuery(object):
    """Class to order and select geocoded locations by matching with a text.

    Attributes:
        corpus:
        threshold:
        exclusions:
        clean:
        vectorizer:

    External methods:
        __call__: Order and select from candidate geocodings by matching to 
           a text.
        cosine: Vectorize texts and compute cosine distance between them.
        get_dists: Extract an array of cosine distances from input geocodings.
        histogram: Return a histogram of dists.
        normed_histogram: Return a histogram of dists, normalized by max_dist.
    """

    # Try threshold=.17 or .2 w/ absolute cosine distance, w/ normed=False
    def __init__(self, corpus=TEXT_CORPUS, threshold=.7, normed=True,
                 exclusions=EXCLUDED_ADDRESS_COMPONENTS, clean=True):
        self.corpus = corpus
        self.threshold = threshold
        self.normed = normed
        self.exclusions = exclusions
        self.clean = clean
        self.vectorizer = None

    def _learn_vectorizer(self, *texts):
        """Learn a text vectorizer from self.corpus plus input texts.

        Output: Assigns self.vectorizer, a bag of words model that outputs
            a normalized vector representation of a text string.
        """
        input_texts = self.corpus + list(texts)
        _, self.vectorizer = prep_text.build_vectorizer(input_texts)

    def __call__(self, locations, text):
        """Order and select from candidate geocodings by matching to a text.

        Before evaluating geocodings, self.vectorizer is relearned
        to ensure that any place names in the text are known in the
        vocabulary.

        The order parameter is cosine distance between vector representations
        of the geocoding address data and the text. Selection is 
        via comparison of cosine distance, normalized by the maximum 
        across cosine distances for the set of locations, with self.threshold.

        Arguments:
            locations: dict whose values are lists of candidate 
                geocodings. geocodings themselves are a dict with 
                address 'components' as a key.
            text: A text string.
        
        Returns: A dict of locations with qualified geocodings
        """
        self._learn_vectorizer(text)
        ordered, selected = {}, {}
        for name, geocodings in locations.items():
            ordered.update({name: self._order_by_distance(geocodings, text)})

        all_distances = [g['cosine_dist'] for geocodings in ordered.values()
                            for g in geocodings]

        if not all_distances:
            if _clean:
                self._scrub_unqualified(ordered)
            return ordered

        max_dist = np.max(all_distances)
        # experiment in progress:
        if not self.normed:
            max_dist = 1
        for name, geocodings in ordered.items():
            dists = self.get_dists(geocodings)
            print('{}\nHistogram: {}\nNormed histogram: {}'.format(
                name, self.histogram(dists),
                self.normed_histogram(dists, max_dist)))
            selected.update({
                name: self._select_by_distance(geocodings, max_dist)})

        if self.clean:
            self._scrub_unqualified(selected)
            self._scrub_components(selected)
        return selected

    def _order_by_distance(self, geocodings, text):
        """Order geocodings by cosine distance of address components to text."""
        for g in geocodings:
            address = self._compile_address(g.get('components', {}))
            g.update({'cosine_dist': self.cosine(address, text)})
        geocodings.sort(key=lambda g:g['cosine_dist'], reverse=True)
        return geocodings
                
    def cosine(self, text1, text2):
        """Vectorize texts and compute cosine distance between them.

        N.b. this function assumes self.vectorizer returns normalized vectors.
    
        Arguments:
            text1, text2: Text strings.

        Returns: Float
        """
        if not self.vectorizer:
            self._learn_vectorizer(text1, text2)
        v1 = self.vectorizer.transform([text1])[0]
        v2 = self.vectorizer.transform([text2])[0]
        return np.dot(v1.A[0], v2.A[0])

    def _compile_address(self, components):
        """Create a text string from address components."""
        joined = ' '.join([v for k,v in components.items()
                               if k not in EXCLUDED_ADDRESS_COMPONENTS
                               and type(v) is str])
        return joined

    def _select_by_distance(self, geocodings, max_dist):
        """Filter geocodings by normalized cosine distance.

        Arguments:
            geocodings: List of candidate geocodings
            max_dist: Cosine distance normalization factor

        Returns: List of qualified geocodings, with cosine_dist popped
        """
        qualified = []
        for g in geocodings:
            normed_dist = g.pop('cosine_dist', 0)/max_dist
            if normed_dist > self.threshold:
                qualified.append(g)
        return qualified

    def _scrub_unqualified(self, locations):
        """Remove locations without qualified geocodings."""
        to_pop = {n for n,g in locations.items() if not g}
        for n in to_pop:
            locations.pop(n)
        
    def _scrub_components(self, locations):
        """Remove raw address components from geocodings."""
        for geocodings in locations.values():
            for g in geocodings:
                g.pop('components', {})

    ### Diagnostic utilities
    def get_dists(self, geocodings):
        """Extract an array of cosine distances from input geocodings."""
        dists = [g.get('cosine_dist') for g in geocodings]
        return np.array([d for d in dists if d is not None])

    def histogram(self, dists, bins=(0,.05,.1,.15,.2,.25,.3,1)):
        """Return a histogram of dists."""
        return np.histogram(dists, bins=bins)[0]
                                               
    def normed_histogram(self, dists, max_dist, hist_range=(0,1)):
        """Return a histogram of dists, normalized by max_dist."""
        return np.histogram(dists/max_dist, range=hist_range)[0]

