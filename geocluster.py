"""Routines to cluster partially geolcated locations.

Classes:
    GeoCluster:  Cluster lat/lon coordinates
    CoreGeoCluster:  Descendant class to find and flesh out a largest
        cluster from input locations, via search of OSM records.

External functions:
    check_near: Determine whether location is within given distance
        of target cluster.
    select_nearest: From proposed geolocations, select nearest to
        target coordinates.
    cluster_plot: Scatterplot clusters of lat/lon coordinates.

Usage:

locations = {
    'Ali Abad hospital': {
        'coords': {'lat': 34.5205639, 'lon': 69.1301792},
        'relevance': 0.659203
    },
    'Kabul': {
        'coords': {'lat': 34.5553494, 'lon': 69.207486},
        'dbpedia': 'http://dbpedia.org/resource/Kabul',
        'relevance': 0.816886
    }
}
gcg = CoreGeoCluster(locations)
core_locations = gcg()

"""
import json
import time

import geopy.distance 
import matplotlib.pyplot as plt
import numpy as np
from shapely import geometry
from sklearn.cluster import DBSCAN

import geolocate

MAX_DIST = 150
MIN_CLUSTER_SIZE = 1

# TODO: Get access to third party Nominatim provider, ref:
# https://wiki.openstreetmap.org/wiki/Nominatim#Details_.2F_Gazetteer
# Then remove instances of this function:
def sleep(seconds=1):
    """Pause so as not to violate Nominatim terms of service"""
    time.sleep(seconds)
    return

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
    
    def __init__(self, max_dist, min_size):
        
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

    
class CoreGeoCluster(GeoCluster):
    """Class to find and augment the largest cluster of input locations.

    (Descendant) Attributes:
        locations: dict with elements of form {loc_name: loc_data}
            where loc_data is a dict that may include 'coords' and
            'relevance' as keys (among others).
            loc_data['coords'] takes form {'lat': lat, 'lon': lon}
        coords: all lat/lon(s) specified in locations in the form of
            an (n,2) numpy array
        
    Public Methods:
        __call__: Determine largest geolocated cluster and augment
            with geolocations for initially unlocated entities.
        augment_cluster: Add previously un-geolocated locations to
            cluster.
        find_largest_cluster: Find largest cluster.
        get_nearest_osm: Get nearest OSM record for input location.
    """
    
    def __init__(self,
                 locations,
                 max_dist=MAX_DIST,
                 min_size=MIN_CLUSTER_SIZE):

        super().__init__(max_dist, min_size)
        # thread-safe deep copy
        self.locations = json.loads(json.dumps(locations))
        try: 
            self.coords = get_coord_array(self.locations)
        except ValueError:
            raise ValueError('No seed coordinates found.')

    def __call__(self):
        """Determine largest geolocated cluster and augment
        with OSM geolocations for initially unlocated entities.
        """
        core_locations = self.find_largest_cluster()
        for loc_name, loc_data in core_locations.items():
            osm = self.get_nearest_osm(loc_name, loc_data)
            loc_data.update({'osm': [osm]})
        core_locations.update(self.augment_cluster(core_locations))
        return core_locations

    def augment_cluster(self, cluster):
        """Add previously ungeolocated places to cluster.

        The routine attempts to geolocate via OSM and adds to
        cluster locations which are within self.max_dist of an
        existing cluster point.

        Argument cluster: dict of locations
        
        Returns: dict of location updates
        """
        unlocated = get_unlocated(self.locations)
        augments = {}
        for loc_name, loc_data in unlocated.items():
            sleep() 
            osm_candidates = geolocate.search_osm(loc_name)
            good_candidates = []
            for cand in osm_candidates:
                if check_near(cand, cluster, max_dist=self.max_dist):
                    good_candidates.append(cand)
            if good_candidates:
                augments.update({loc_name: {'osm': good_candidates}})
        return augments

    def find_largest_cluster(self, coord_clusters=None):
        """Find largest cluster.

        Routine selects by summed relevance scores if there are multiple
            clusters of equal maximum size.

        Argument:  list of (n,2) numpy arrays of lat/lon(s)

        Returns:  Dict of locations.
        """
        if coord_clusters is None:
            coord_clusters = super().cluster(self.coords)
        max_size = np.max([len(c) for c in coord_clusters])
        max_cc = [c for c in coord_clusters if len(c) == max_size]
        max_locations = []
        for mc in max_cc:
            locations = self._filter_coords(mc)
            relevance = np.sum([v['relevance']
                                for v in locations.values()])
            max_locations.append((locations, relevance))
        max_locations.sort(key=lambda loc: loc[1], reverse=True)
        return max_locations[0][0]

    def get_nearest_osm(self, loc_name, loc_data):
        """Retrieve nearest search result from OSM.

        Arguments:
            loc_name type: str
            loc_data: dict containing
                {'coords': {'lat': lat, 'lon': lon}}

        Returns: OSM dict
        """
        sleep()
        osm_candidates = geolocate.search_osm(loc_name)
        coords = get_coord_array({loc_name: loc_data})
        osm_rec = select_nearest(osm_candidates, coords,
                                 max_dist=self.max_dist)
        return osm_rec

    def _filter_coords(self, coords):
        """Return locations for which lat/lon appear in input coords.

        The routine requires an exact lat/lon match, so assumes
        lat/lon have previously been extracted from self.locations.

        Argument coords: numpy array of lat/lon(s), shape (n,2).

        Returns: dict of locations
        """
        good_locations = {}
        for k,v in self.locations.items():
            try:
                if (v['coords']['lat'], v['coords']['lon']) in coords:
                    good_locations.update({k:v})
            except KeyError:
                pass
        return good_locations

    
# Helper functions to manipulate locations dicts

def get_unlocated(locations):
    """Extract locations that have no geolocation.

    Argument locations: dict 

    Returns: subdict 
    """
    unlocated = {}
    for loc_name, loc_data in locations.items():
        if 'coords' not in loc_data.keys():
            unlocated.update({loc_name: loc_data})
    return unlocated
    
def get_coord_array(locations):
    """Extract available lat/lon from locations dict.

    Argument locations:  dict
    
    Returns: numpy array of shape (n,2)
    """
    coords = []
    for l in locations.values():
        try:
            latlon = l['coords']
            coords.append((float(latlon['lat']),
                               float(latlon['lon'])))
        except KeyError:
            pass
    if len(coords) == 0:
        raise ValueError('No geolocations provided.')
    return np.array(coords)


# Functions to compute / select by distance on the Earth's surface

def check_near(geoloc_proposal, cluster, max_dist=MAX_DIST):
    """Check that geoloc_proposal is withing max_dist of cluster.

    Arguments:
        geoloc_proposal: dict with lat, lon as keys
            (typically, an OSM record)
        cluster: dict of locations
        max_dist: max accpetable distance form any point in the cluster
            in km

    Returns:  True if within max_distance else False
    """
    lat = float(geoloc_proposal['lat'])
    lon = float(geoloc_proposal['lon'])
    coord_cluster = get_coord_array(cluster)
    for target_coords in coord_cluster:
        dist = geopy.distance.great_circle((lat, lon), target_coords)
        if dist.kilometers <= max_dist:
            return True
    return False

def select_nearest(geoloc_proposals, target_coords, max_dist):
    """Select from among geolocation proposals.

    The proposal nearest to target_coords is returned, but only if
        within max_dist.

    Arguments:
        geoloc_proposals: list of dicts with lat, lon as keys
            (typically, OSM records)
        target_coords: tuple (lat, lon)
        max_dist: max accpetable distance form target_coords in km

    Returns: dict
    """
    if len(geoloc_proposals) == 0:
        return {}
    proposals_dists = []
    for gp in geoloc_proposals:
        lat, lon = float(gp['lat']), float(gp['lon'])
        dist = geopy.distance.great_circle((lat, lon), target_coords)
        proposals_dists.append((gp, dist.kilometers))
    proposals_dists.sort(key=lambda pd: pd[1])
    best_proposal, least_dist = proposals_dists[0]
    return best_proposal if least_dist <= max_dist else {}


# Utility to plot geoclusters

def cluster_plot(coord_clusters, save_prefix, scaling=10):
    """Scatterplot clusters of lat/lon coords.

    Arguments:
        clusters: numpy array of shape (n,2)
        save_prefix: text string
        scaling: graph points have area proportional to cluster size,
            scaled up by this factor

    Output: Writes scatterplot to save_prefix.png.
    """
    fig, ax = plt.subplots()
    cluster_sizes = [len(c) for c in coord_clusters]
    centroids = [geometry.MultiPoint(c).centroid
                 for c in coord_clusters]
    centroids_x = [cen.x for cen in centroids]
    centroids_y = [cen.y for cen in centroids]
    cluster_scatter = ax.scatter(centroids_x, centroids_y,
                            c='#99cc99', edgecolor='None',
                            alpha=0.7,
                            s=scaling*np.array(cluster_sizes))
    ax.set_title('Coordinate clusters')
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    plt.savefig(save_prefix+'.png', bbox_inches='tight') 
    return

