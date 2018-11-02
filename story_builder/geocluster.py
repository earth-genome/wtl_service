"""Routines to cluster geographic locations.  

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

The logic of growing a cluster with OpenStreetMap (OSM) data after
seeding with Google Places API data is that the latter seems relatively
terse in its responses, while OSM is so verbose as to be almost useless
without some prior sense of the relevant region in which to search.

Usage:
> ggc = GrowGeoCluster()
> seeds = ggc.seed(locations)
> clusters = ggc.grow(seeds, candidated_locations)

External classes:
    GeoCluster:  Cluster lat/lon coordinates
    GrowGeoCluster:  Descendant class to find clusters of input locations.


"""
import json

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
        
    Descendant Methods:
        seed: Geolocate and cluster initial locations.
        grow: Add places with candidate geolocations to clusters.
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def seed(self, locations):
        """Cluster locations. Returns a list of subdicts of locations."""
        try: 
            coords = coords_from_locations(locations)
        except ValueError as e:
            raise ValueError('No seed coordinates found.') 
        coord_clusters = super().cluster(coords)
        seeds = [locations_from_coords(cc, locations) for cc in coord_clusters]
        return seeds

    def grow(self, clusters, candidated):
        """Add places with candidate geolocations to clusters.

        The routine adds to a cluster the candidate locations which are
        sufficiently close to an existing cluster. Since geolocations in 
        candidated places are ranked, the first viable cluster placement is 
        accepted and considered thenceforth as the resolved geolocation for 
        that place.

        Arguments:
            clusters: list of dicts of locations
            candidated: dict with lists of geolocation 'candidates' in values
        
        Returns: updated list of dicts of locations
        """
        clusters = json.loads(json.dumps(clusters))
        for name, data in candidated.items():
            candidates = data.pop('candidates')
            for geoloc in candidates:
                cluster_idx = self._match_to_cluster(geoloc, clusters)
                if cluster_idx is not None:
                    clusters[cluster_idx].update({name: dict(data, **geoloc)})
                    break
            else:
                clusters.append({name: dict(data, **candidates[0])})
        return clusters

    def _match_to_cluster(self, geolocation, clusters):
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
        for n, cluster in enumerate(clusters):
            if len(cluster) > 0:
                if (self._check_intersects(geolocation, cluster) or
                    self._check_near(geolocation, cluster)):
                    return n
        return

    def _check_intersects(self, geolocation, cluster):
        """Check whether geolocation intersects any location in cluster."""
        try: 
            source = geometry.box(*geolocation['boundingbox'])
        except KeyError:
            source = geometry.Point(geolocation['lon'], geolocation['lat'])
        for data in cluster.values():
            try:
                target = geometry.box(*data['boundingbox'])
            except KeyError:
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
