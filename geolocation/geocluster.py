"""Routines to cluster geographic locations and select from candidate
geocodings based on clustering.  

See geolocate.py for notes on input location data and formatting.  

The base class GeoCluster is a lightweight affair which operates
directly on latitude/longitude coordinates given in an (n,2) numpy
array.

Simple use of this base class might entail, on input array coords:
> gc = GeoCluster(max_dist=150, min_size=1)
> coord_clusters = gc.cluster(coords)
> import geoclusterplot  # outside this repo
> geoclusterplot.cluster_plot(coord_clusters, 'scatterplot.png')

The descendant class GrowGeoCluster handles locations dicts of form
specified in geolocate.py, bulkier in its machinations to handle 
tentative lat/lon assignments.

Usage:
> ggc = GrowGeoCluster()
> clusters = ggc.(locations)

External classes:
    GeoCluster:  Cluster lat/lon coordinates
    GrowGeoCluster:  Descendant class to find clusters of input locations.


"""
import json
import random

import geopy.distance 
import numpy as np
from shapely import geometry
from sklearn.cluster import DBSCAN

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
