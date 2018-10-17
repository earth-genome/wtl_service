"""Routines to cluster locations.

The fundamental entity worked on by these routines is a dict, often
taking variable name 'locations' (also sometimes 'places', if not yet
geolocated, or 'cluster') of the following form(s):

Initially as input:
places = 
{'Maputo': {'dbpedia': 'http://dbpedia.org/resource/Maputo',
  'relevance': 0.846839,
  'subtype': ['AdministrativeDivision', 'City']},
 'Mozambique': {'dbpedia': '',
  'relevance': 0.484892,
  'subtype': ['StateOrCounty']}}

Final output:
core_locations =
{'Maputo, Mozambique': {'address': 'Maputo, Mozambique',
   'boundingbox': (32.5233079, -25.9839715, 32.6980592, -25.8085457),
   'dbpedia': 'http://dbpedia.org/resource/Maputo',
   'lat': -25.969248,
   'lon': 32.5731746,
   'name': 'Maputo',
   'relevance': 0.846839,
   'source': 'google',
   'subtype': ['AdministrativeDivision', 'City'],
   'types': ['locality', 'political']}}
   
The 'relevance' key is expected for use in scoring (selecting among) clusters.
Other keys are allowed.

That said, the base class GeoCluster is a lightweight affair which
operates directly on latitude/longitude coordinates given in
an (n,2) numpy array.

Simple use of this base class might entail, on input array coords:
> gc = GeoCluster(max_dist=150, min_size=1)
> coord_clusters = gc.cluster(coords)
> import geoclusterplot  # outside this repo
> geoclusterplot.cluster_plot(coord_clusters, 'scatterplot.png')

The descendant class GrowGeoCluster handles locations of form
specified above, bulkier in its machinations to handle incomplete data.
(The logic of growing a cluster with OpenStreetMap (OSM) data after
seeding with Google Places API data is that the latter seems relatively
terse in its responses, while OSM is so verbose as to be almost useless
without some prior sense of the relevant region in which to search.)

Usage:
> ggc = GrowGeoCluster(classifier=geocluster.score)
> core_locations, clusters = ggc.seed_and_grow(places)

Classes:
    GeoCluster:  Cluster lat/lon coordinates
    GrowGeoCluster:  Descendant class to find clusters of input places.

External functions:
    # geocoding wrappers
        geocode
        dbpedia_constrained_coding
    # Helper functions to manipulate locations dicts
        coords_from_locations
        locations_from_coords
        get_centroid
    # Functions to compute / select by distance on the Earth's surface
        check_near
        sort_by_distance

"""
import json
import time

import geopy.distance 
import numpy as np
from shapely import geometry
from sklearn.cluster import DBSCAN

from story_builder import geolocate
from utilities.geobox import geobox

MAX_DIST = 150
MIN_CLUSTER_SIZE = 1

#CLASSIFIER = GrowGeoCluster()._score

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
    
    def __init__(self, max_dist=MAX_DIST, min_size=MIN_CLUSTER_SIZE):
        
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
    """Class to geolocate and cluster named places.

    (Descendant) Attributes:
        terse_geocoder, verbose_geocoder: functions from geolocate module
        classifier: function to score cluster quality 
            (or None; default: self._score)
        
    Public Methods:
        __call__: Geolocate, cluster, grow and score clusters.
        seed: Geolocate and cluster initial locations.
    """
    
    def __init__(self,
                 max_dist=MAX_DIST,
                 min_size=MIN_CLUSTER_SIZE,
                 terse_geocoder=geolocate.google_geocode,
                 verbose_geocoder=geolocate.osm_geocode,
                 classify=True):
        super().__init__(max_dist, min_size)
        self.terse_geocoder = terse_geocoder
        self.verbose_geocoder = verbose_geocoder
        self.classifier = None if not classify else self._score

    def __call__(self, places):
        """Geolocate, cluster, and score clusters.

        Returns: list of dicts
        """
        good_clusters = []

        # iterative geocoding
        locations, unlocated = geocode(places, geocoder=self.terse_geocoder)
        new_locations, unlocated = dbpedia_constrained_coding(unlocated,
                                    geocoder=self.verbose_geocoder)
        locations.update(new_locations)
        third_gen, unlocated = geocode(unlocated,
                                       geocoder=self.verbose_geocoder)

        # clustering
        clusters = self.seed(locations)
        for cluster in clusters:
            cluster.update(self._grow(cluster, third_gen))
            if self.classifier:
                if self.classifier(cluster) == 0:
                    continue
            good_clusters.append(cluster)
        return self._present(good_clusters)

    def seed(self, locations):
        """Cluster initial locations.

        Argument locations: dict
        
        Returns: list of cluster dicts
        """
        try: 
            coords = coords_from_locations(locations)
        except ValueError as e:
            raise ValueError('No seed coordinates found.') 
        coord_clusters = super().cluster(coords)
        clusters = [locations_from_coords(coord_cluster, locations)
                    for coord_cluster in coord_clusters]
        return clusters

    def _grow(self, cluster, recodes):
        """Add preliminarily unlocated places to cluster.

        The routine adds to cluster the recoded locations which are within
        self.max_dist of an existing cluster point.

        Arguments
            cluster: dict of locations
            recodes: dict of locations
        
        Returns: subdict of recoded locations to update cluster
        """
        new_locations = {}
        for name, data in recodes.items():
            if check_near(data, cluster, max_dist=self.max_dist):
                new_locations.update({name: data})
        return new_locations

    # WIP: ad hoc cluster scoring to be replaced with a classifier
    def _score(self, cluster):
        """Ad hoc cluster scoring."""
        SCORE_THRESH = .5
        SIZE_THRESH = 40 # km
        unique_names, relevance_scores, sizes = [], [], []
        for data in cluster.values():
            try:
                size = geobox.get_side_distances(
                    geometry.box(*data['boundingbox']))
                sizes.append(np.mean(size))
            except KeyError:
                pass
            if data['name'] in unique_names:
                continue
            try:
                relevance_scores.append(data['relevance'])
                unique_names.append(data['name'])
            except KeyError:
                pass
        min_size = np.min(sizes)
        score = len(unique_names) * np.mean(relevance_scores)
        return score if score > SCORE_THRESH and min_size < SIZE_THRESH else 0
    
    def _present(self, clusters):
        """Record cluster metadata and flatten clusters to a dict of locations.

        Argument clusters: list of dicts

        Returns: dict of locations, list of cluster metadata
        """
        metadata = []
        for cluster in clusters:
            metadata.append({
                'centroid': get_centroid(cluster),
                'locations': [name for name in cluster.keys()]
            })
            if self.classifier:
                metadata[-1].update({
                    'score': self.classifier(cluster)
                })
        locations = {name:data for cluster in clusters
                     for name, data in cluster.items()}
        return locations, metadata
    

# Geocoding wrappers

def geocode(places, geocoder):
    """Find geo-coordinates for input places.

    Arguments:
        places: dict with place names as keys
        geocoder: Function from geolocate module

    Returns: dicts of places located and unlocated
    """
    located, unlocated = {}, {}
    for name, data in places.items():
        geolocs = geocoder(name)
        if not geolocs:
            unlocated.update({
                name: {
                    'name': name,
                    **data
                }
            })
        else:
            for geoloc in geolocs:
                located.update({
                    geoloc['address']: {
                        'name': name,
                        **data,
                        **geoloc
                    }
                })
    return located, unlocated

def dbpedia_constrained_coding(places, geocoder):
    """Use a dbpedia reference to constrain a search with (verbose) geocoder.

    Arguments:
        places: dict with place names as keys
        geocoder: Function from geolocate module

    Returns: dicts of places located and unlocated
    """
    located, unlocated = {}, {}
    for name, data in places.items():
        try:
            target = geolocate.dbpedia_geocode(data['dbpedia'])
        except KeyError:
            target = {}
        if not target:
            unlocated.update({
                name: {
                    'name': name,
                    **data
                }
            })
        else:
            lat, lon = target['lat'], target['lon']
            geolocs = geocode({name: data}, geocoder)[0]
            if len(geolocs) > 0: 
                nearest = next(iter(sort_by_distance(geolocs, lat, lon)))[0]
                box = geometry.box(*list(nearest.values())[0]['boundingbox'])
                if box.intersects(geometry.Point(lon, lat)): 
                    located.update(nearest)
            else:
                located.update({
                    target['address']: {
                        'name': name,
                        **data,
                        **target
                    }
                })
    return located, unlocated

    
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
    """Find locations dict items for given array of lat/lon coords.

    This routine inverts coords_from_locations(). It seeks an exact
    lat/lon match between elements of coords and locations.

    Arguments:
        coords: numpy array of lat/lon(s), shape (n,2).
        locations: dict

    Returns: dict of locations
    """
    good_locations = {}
    for name, data in locations.items():
        try:
            if (data['lat'], data['lon']) in coords:
                good_locations.update({name: data.copy()})
        except KeyError:
            pass
    return good_locations

def get_centroid(cluster):
    """Find centroid of cluster points.

    Argument cluster: dict of locations

    Returns: dict with lat/lon
    """
    # WIP: redo after harmonizing google/osm locations
    points = []
    for data in cluster.values():
        try:
            points.append((data['lon'], data['lat']))
        except KeyError:
            pass
    centroid = geometry.MultiPoint(points).centroid
    return {'lat': centroid.y, 'lon': centroid.x}

# Functions to compute / select by distance on the Earth's surface

def check_near(location, cluster, max_dist=MAX_DIST):
    """Check that location is withing max_dist of cluster.

    Arguments:
        location: dict with 'lat', 'lon' as keys
        cluster: dict of locations
        max_dist: max accpetable distance form any point in the cluster
            in km

    Returns:  True if within max_distance else False
    """
    lat, lon = location['lat'], location['lon']
    coord_cluster = coords_from_locations(cluster)
    for target_coords in coord_cluster:
        dist = geopy.distance.great_circle((lat, lon), target_coords)
        if dist.kilometers <= max_dist:
            return True
    return False

def sort_by_distance(locations, lat, lon):
    """Sort locations by least distance from lat, lon.

    Arguments:
        locations: dict
        lat, lon type: float

    Returns: list of tuples of locations and distances
    """
    loc_distances = []
    for name, data in locations.items():
        dist = geopy.distance.great_circle((data['lat'], data['lon']),
                                           (lat, lon))
        loc_distances.append(({name: data.copy()}, dist.kilometers))
    loc_distances.sort(key=lambda d: d[1])
    return loc_distances

