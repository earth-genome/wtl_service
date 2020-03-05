"""Routines to geocode and score relevance of locations to satellite-based 
reporting. 

The fundamental entity worked on by these routines is a dict, often
taking variable name 'locations' (also sometimes 'places', if not yet
geocoded, or 'cluster'). 

On input, the following keys are required:
'text': string (the place name as it appears in a story)
'relevance': float in [0,1] 
'mentions': list of strings (sentences in which the 'text' appears in a story)

The last can be extracted with the find_mentions function, included in this 
module because the limit parameter impacts classifier architecture.

External classes: 
    Geolocate: Geolocate and score locations.
    BackQuery: Order and select geocoded locations by matching with a text.
    GeoCluster: Cluster lat/lon coordinates
    GrowGeoCluster: Descendant class to find clusters of input locations.

External function: 
    find_mentions: Extract sentences where place is mentioned in text.

Usage with defaults and a served classifier: 
> locator = geolocate.Geolocate(model_url='http://52.34.232.26/locations') 
> locator(places)


"""

from collections import OrderedDict
from inspect import getsourcefile
import json
import os
import random

import geopy.distance 
import nltk
import numpy as np
import requests
from shapely import geometry
from sklearn.cluster import DBSCAN

from bagofwords import prep_text
import geocode

base_dir = os.path.dirname(os.path.abspath(getsourcefile(lambda:0)))
with open(os.path.join(base_dir, 'bagofwords/WTLtrainingtexts.txt')) as f:
    TEXT_CORPUS = [l.strip() for l in f]

EXCLUDED_ADDRESS_COMPONENTS = ['ISO_3166-1_alpha-2', 'ISO_3166-1_alpha-3',
    '_category', '_type', 'country_code', 'road_type', 'postcode']

MAX_MENTIONS = 6

def find_mentions(place, text, limit=MAX_MENTIONS):
    """Extract sentences where place is mentioned in text.
    
    Arguments:
        place: string to find in sentences of text
        text: long string to be split into sentences

    Returns: list of sentences
    """
    sentences = nltk.sent_tokenize(text)
    mentions = [s for s in sentences if place in s]
    return mentions[:limit]

class Geolocate(object):
    """Class to geolocate and score locations.

    Attributes:
        geocoders: list of functions from geocode module
        cluster_tool: instance of GrowGeoCluster class
        model_url: Url pointing to served model, or None

    External methods: 
        __call__: Geocode, cluster, and score input places.
        assemble_geocodings: Find geo-coordinates with geocoders in sequence.
        classify_relevance: Hit served model to determine relevance of 
            locations.
    """
    def __init__(self, geocoders=[], backquery=None, cluster_tool=None,
                 model_url=None):
        self.geocoders = geocoders if geocoders else [geocode.CageCode()]
        self.backquery = backquery if backquery else BackQuery()
        if cluster_tool:
            self.cluster_tool = cluster_tool
        else:
            self.cluster_tool = GrowGeoCluster()
        self.model_url = model_url

    def __call__(self, places, text):
        """Geocode, cluster, and score input places.

        Returns: dict of locations
        """
        candidates = self.assemble_geocodings(places)
        candidates = self.backquery(candidates, text)
        if not candidates:
            raise ValueError('No candidate coordinates found.')
        clusters = self.cluster_tool(candidates)

        for cluster in clusters:
            for name, data in cluster.items():
                data.update({
                    'cluster': list(cluster),
                    'cluster_ratio': len(cluster)/len(candidates),
                    **places[name]
                })

        locations = {k:v for cluster in clusters for k,v in cluster.items()}

        if self.model_url:
            locations = self.classify(locations)

        return locations
        
    def assemble_geocodings(self, places):
        """Find geo-coordinates with (possibly multiple) geocoders.

        Returns: dicts of places with candidate geocodings
        """
        candidates = {}
        for name, data in places.items():
            geolocs = []
            for geocoder in self.geocoders:
                try:
                    geolocs += geocoder(name)
                except Exception as e:
                    print('Geocoding {}: {}'.format(name, repr(e)), flush=True)
            if geolocs:
                candidates.update({name: geolocs})
        return candidates

    def classify(self, locations):
        """Hit served model to determine relevance of locations."""
        ordered_locs = OrderedDict(locations)
        response = requests.post(
            self.model_url,
            data={'locations_data': json.dumps(list(ordered_locs.values()))})
        try:
            response.raise_for_status()
        except requests.RequestException:
            raise requests.RequestException(response.text)

        for scores, data in zip(response.json(), ordered_locs.values()):
            data.update({'map_relevance': scores})
            
        return dict(ordered_locs)

class BackQuery(object):
    """Class to order and select geocoded locations by matching with a text.

    Attributes:
        corpus: List of strings: The bulk of the content on which to train
            the vectorizer
        threshold: Minimum cosine distance to qualify a geocoding
        exclusions: Geocoding address components to ignore
        clean: bool: Whether to excise null geocodings and address components
            after backquery
        vectorizer: A bag of words model for the corpus plus input text

    External methods:
        __call__: Order and select from candidate geocodings by matching to 
           a text.
        cosine: Vectorize texts and compute cosine distance between them.
    """
    def __init__(self, corpus=TEXT_CORPUS, threshold=.1, 
                 exclusions=EXCLUDED_ADDRESS_COMPONENTS, clean=True):
        self.corpus = corpus
        self.threshold = threshold
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
        vocabulary. The order and selection parameter is cosine distance 
        between vector representations of the geocoding address data and the 
        text. 

        Arguments:
            locations: dict whose values are lists of candidate 
                geocodings. geocodings themselves are a dict with 
                address 'components' as a key.
            text: A text string.
        
        Returns: A dict of locations with qualified geocodings
        """
        self._learn_vectorizer(text)
        locations = json.loads(json.dumps(locations))
        ordered = {name: self._match(geocodings, text) for name, geocodings
                        in locations.items()}

        if self.clean:
            self._scrub_unqualified(ordered)
            self._scrub_components(ordered)
        return ordered

    def _match(self, geocodings, text):
        """Select and sort geocodings by cosine distance to text."""
        qualified = []
        for g in geocodings:
            address = self._compile_address(g.get('components', {}))
            distance = self.cosine(address, text)
            if distance > self.threshold:
                qualified.append([g, distance])
        qualified.sort(key=lambda q:q[1], reverse=True)
        return [q[0] for q in qualified]
                
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


class GeoCluster(object):
    """Class to cluster lat/lon coordinates.

    Attributes:
        max_dist:  maximum distance between cluster points in km
        max_radians:  max_dist converted to radians (approximately,
            with Earth's surface assumed spherical)
        min_size: minimum number of elements to create a cluster

    Method:
        cluster: cluster input coordinates
    """
    
    def __init__(self, max_dist=150, min_size=1):
        
        self.max_dist = max_dist
        self.max_radians = max_dist/geopy.distance.EARTH_RADIUS
        self.min_size = min_size

    def cluster(self, coords):
        """Cluster (lat/lon) coords.

        Argument coords:  numpy array of shape (n,2)

        Returns: list of coordinate arrays
        """
        db = DBSCAN(eps=self.max_radians,
                    min_samples=self.min_size,
                    algorithm='ball_tree',
                    metric='haversine').fit(np.radians(coords))
        # unclustered points have label -1
        good_labels = set([l for l in db.labels_ if l >=0])
        coord_clusters = [coords[db.labels_ == n] for n in good_labels]
        return coord_clusters

class GrowGeoCluster(GeoCluster):
    """Class to cluster named locations.

    Descendant attributes, set within grow() during optimization: 
            clusters: list of location dicts
            cluster_lens: list of lengths of location dicts
            gain: gain of current cluster configuration
            name: location under trial
            idx: cluster list index for location under trial
        
    Descendant methods:
        seed: Cluster initial locations.
        grow: Optimize cluster size by trying candidate geolocations.
        __call__: Determine best geolocations from candidates.
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __call__(self, candidates):
        """Determine best geolocations from candidates."""
        init_locations = {name:locs[0] for name,locs in candidates.items()}
        seeds = self.seed(init_locations)
        return self.grow(seeds, candidates)
        
    def seed(self, locations):
        """Cluster locations. Returns a list of subdicts of locations."""
        coord_clusters = super().cluster(coords_from_locations(locations))
        seeds = [locations_from_coords(cc, locations) for cc in coord_clusters]
        return seeds

    def grow(self, clusters, candidates):
        """Optimize cluster size by trying candidate geolocations.
        
        This heuristic optimizer assumes locations in news stories tend to
        cluster, and correctly geocoded locations will yield larger clusters.

        Moves are accepted if the candidate location is sufficiently close 
        to an existing cluster and it increases mean squared cluster size. 

        Arguments:
            clusters: list of dicts of locations
            candidates: dict with lists of geolocations for values
        
        Returns: updated clusters
        """
        self.clusters = json.loads(json.dumps(clusters))
        while True:
            random.shuffle(self.clusters)
            self._set_gain()
            gain0 = self.gain
            
            for name, data in candidates.items():
                self.name = name
                self.idx = self._get_idx(name)
                for geoloc in data:
                    self._try_move(geoloc)
                    
            if self.gain == gain0:
                break
            
        return [cluster for cluster in self.clusters if cluster]

    def _set_gain(self):
        """Set cluster_lens and gain after modifying clusters."""
        self.cluster_lens = [len(c) for c in self.clusters]
        self.gain = self._measure_gain(self.cluster_lens)
    
    def _measure_gain(self, lens):
        """Compute mean squared length (times irrelevant normaliz. factor)."""
        return sum([l**2 for l in lens])

    def _get_idx(self, name):
        """Extract list index for position of name in self.clusters."""
        idx = [n for n,c in enumerate(self.clusters) if name in c]
        return idx[0]

    def _trial_lens(self, trial_idx):
        """Compute clusters lengths as they would be if move were accepted."""
        trial_lens = self.cluster_lens.copy()
        trial_lens[trial_idx] += 1
        trial_lens[self.idx] -= 1
        return trial_lens

    def _update(self, geoloc, trial_idx):
        """Accept move. Adjust state attributes accordingly."""
        self.clusters[self.idx].pop(self.name)
        self.clusters[trial_idx].update({self.name: geoloc})
        self.idx = trial_idx
        self._set_gain()
                                 
    def _try_move(self, geoloc):
        """Evaluate move conditions and update state if move is accepted."""
        trial_idx = self._match_to_cluster(geoloc)
        if trial_idx is not None:
            trial_lens = self._trial_lens(trial_idx)
            if self._measure_gain(trial_lens) > self.gain:
                self._update(geoloc, trial_idx)
        return

    def _match_to_cluster(self, geolocation):
        """Attempt to match geolocation to a proximal cluster.

        A geolocation is considered to match to a cluster if it either 
        intersects one of the cluster's locations or if its lat, lon
        is within self.max_dist of the lat, lon of one of the cluster's
        locations. The first cluster to match is accepted.

        Arguments:
            geolocation: dict with 'lat', 'lon' as keys
            clusters: list of dicts of locations

        Returns: List index of matched cluster, if available, or None
        """
        for n, cluster in enumerate(self.clusters):
            if n != self.idx and len(cluster) > 0:
                if (self._check_intersects(geolocation, cluster) or
                    self._check_near(geolocation, cluster)):
                    return n
        return

    def _check_intersects(self, geolocation, cluster):
        """Check whether geolocation intersects any location in cluster."""
        try: 
            source = geometry.box(*geolocation.get('boundingbox'))
        except TypeError:
            source = geometry.Point(geolocation['lon'], geolocation['lat'])
        for data in cluster.values():
            try:
                target = geometry.box(*data.get('boundingbox'))
            except TypeError:
                target = geometry.Point(data['lon'], data['lat'])
            if source.intersection(target).bounds:
                return True
        return False

    def _check_near(self, geolocation, cluster):
        """Check that geolocation is withing max_dist of a cluster point."""
        lat, lon = geolocation['lat'], geolocation['lon']
        coord_cluster = coords_from_locations(cluster)
        for target_coords in coord_cluster:
            dist = geopy.distance.great_circle((lat, lon), target_coords)
            if dist.kilometers <= self.max_dist:
                return True
        return False
        
# Helper functions to manipulate locations dicts
    
def coords_from_locations(locations):
    """Extract available lat/lon from locations dict.
    
    Returns: numpy array of shape (n,2)
    """
    coords = []
    for data in locations.values():
        try:
            coords.append((data['lat'], data['lon']))
        except KeyError:
            pass
    if len(coords) == 0:
        raise ValueError('No lat/lon(s) found.')
    return np.array(coords)

def locations_from_coords(coords, locations):
    """Find locations dict items corresponding to given array of lat/lon coords.

    This routine inverts coords_from_locations(). It seeks an exact
    lat/lon match between elements of coords and locations.

    Arguments:
        coords: numpy array of lat/lon(s), shape (n,2).
        locations: dict

    Returns: subdict of locations
    """
    good_locations = {}
    for name, data in locations.items():
        try:
            if (data['lat'], data['lon']) in coords:
                good_locations.update({name: data.copy()})
        except KeyError:
            pass
    return good_locations
