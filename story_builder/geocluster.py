"""Routines to cluster (partly) geolcated locations.

The fundamental entity worked on by these routines is a dict, often
taking variable name 'locations', of the following form:

{'Ginzan Onsen': {'coords': {'lat': 38.5704041, 'lon': 140.5304678},
  'relevance': 0.824213},
 'Ginzan River': {'coords': {'lat': 38.5704041, 'lon': 140.5304678},
  'relevance': 0.365675},
 'Japan': {'coords': {'lat': 36.204824, 'lon': 138.252924},
  'dbpedia': 'http://dbpedia.org/resource/Japan',
  'relevance': 0.755042},
 'Nobezawa Ginzan Silver Mine': {'relevance': 0.391877},
 'North Hokkaido': {'coords': {'lat': 43.2203266, 'lon': 142.8634737},
  'relevance': 0.270608},
 'South Okinawa': {'coords': {'lat': 26.2124013, 'lon': 127.6809317},
  'relevance': 0.257954},
 'Tohoku': {'relevance': 0.251835, 'subtype': ['City']}}

The 'relevance' key is expected for use in selecting among clusters.
'coords' is expected for at least one of the given locations.
Other keys are allowed.

A subdict might be passed with name 'clusters' or 'core_locations'.

That said, the base class GeoCluster is a lightweight affair which
operates directly on latitude/longitude coordinates given in
an (n,2) numpy array.

Simple use of this base class might entail, on input array coords:
> gc = GeoCluster(max_dist=150, min_size=1)
> coord_clusters = gc.cluster(coords)
> cluster_plot(coord_clusters, 'scatterplot.png')

The descendant class GrowGeoCluster handles locations of form
specified above, bulkier in its machinations to handle incomplete data.
(The logic of growing a cluster with OpenStreetMap (OSM) data after
seeding with Google Places API data is that the latter seems relatively
terse in its responses, while OSM is so verbose as to be almost useless
without some prior sense of the relevant region in which to search.)

Usage:
> ggc = GrowGeoCluster(locations)
> core_locations = ggc.seed_and_grow()

Classes:
    GeoCluster:  Cluster lat/lon coordinates
    GrowGeoCluster:  Descendant class to find and flesh out a largest
        cluster from input locations, via search of OSM records.

External functions:
    check_near: Determine whether location is within given distance
        of target cluster.
    select_nearest: From proposed geolocations, select nearest to
        target coordinates.
    cluster_plot: Scatterplot clusters of lat/lon coordinates.

"""
import json
import time

import geopy.distance 
import matplotlib.pyplot as plt
import numpy as np
from shapely import geometry
from sklearn.cluster import DBSCAN

from . import geolocate

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
    """Class to find and augment the largest cluster of input locations.

    (Descendant) Attributes:
        locations: dict with elements of form {loc_name: loc_data}
            where loc_data is a dict that may include 'coords' and
            'relevance' as keys (among others).  
            loc_data['coords'] takes form {'lat': lat, 'lon': lon}
        coords: (n,2) array of available lat/lon coordinates in
            locations
        unlocated: initially unlocated entities drawn from locations 
        
    Public Methods:
        seed: Find a return a deep copy of largest cluster of locations.
        seed_and_grow: Determine largest geolocated cluster, add OSM
            records, and augment with geolocations for initially
            unlocated entities.
        augment_cluster: Add previously unlocated entities to
            cluster.
        get_nearest_osm: Get nearest OSM record for input location.
    """
    
    def __init__(self,
                 locations,
                 max_dist=MAX_DIST,
                 min_size=MIN_CLUSTER_SIZE):
        super().__init__(max_dist, min_size)
        # thread-safe deep copy
        self.locations = json.loads(json.dumps(locations))
        self.unlocated = get_unlocated(self.locations)
        try: 
            self.coords = get_coord_array(self.locations)
        except ValueError as e:
            raise ValueError('No seed coordinates found.') from e

    def seed(self):
        """Find and return deep copy of largest cluster."""
        seed_locations = self._find_largest_cluster()
        return json.loads(json.dumps(seed_locations))

    def seed_and_grow(self):
        """Determine largest geolocated cluster, add OSM records,
        and augment with OSM geolocations for initially unlocated
        entities.

        Returns: dict
        """
        core_locations = self.seed()
        for loc_name, loc_data in core_locations.items():
            osm = self.get_nearest_osm(loc_name, loc_data)
            loc_data.update({'osm': [osm]})
        core_locations.update(self.augment_cluster(core_locations))
        return core_locations

    def augment_cluster(self, cluster):
        """Add previously unlocated places to cluster.

        The routine attempts to geolocate via OSM and adds to
        cluster new locations which are within self.max_dist of an
        existing cluster point.

        Argument cluster: dict of locations
        
        Returns: dict of location updates
        """
        additions = {}
        for loc_name, loc_data in self.unlocated.items():
            sleep() 
            osm_candidates = geolocate.search_osm(loc_name)
            good_candidates = []
            for cand in osm_candidates:
                if check_near(cand, cluster, max_dist=self.max_dist):
                    good_candidates.append(cand)
            if good_candidates:
                additions.update({loc_name: {'osm': good_candidates}})
        return additions

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
        osm_rec = select_nearest(osm_candidates, {loc_name: loc_data},
                                 max_dist=self.max_dist)
        return osm_rec

    def _find_largest_cluster(self):
        """Find largest cluster.

        Routine selects by summed relevance scores if there are multiple
            clusters of equal maximum size.

        Argument locations: dict

        Returns:  Subdict of locations.
        """
        coord_clusters = super().cluster(self.coords)
        max_size = np.max([len(c) for c in coord_clusters])
        max_cc = [c for c in coord_clusters if len(c) == max_size]
        max_locations = []
        for mc in max_cc:
            locs = self._filter_coords(mc)
            try: 
                relevance = np.sum([v['relevance']
                                    for v in locs.values()])
            except KeyError:
                raise KeyError('Missing relevance scores.') from e
            max_locations.append((locs, relevance))
        max_locations.sort(key=lambda loc: loc[1], reverse=True)
        return max_locations[0][0]

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

def select_nearest(geoloc_proposals, target_location, max_dist):
    """From geolocation proposals, select nearest to target_location.

    The proposal nearest to target_location is returned only if
        within max_dist.

    Arguments:
        geoloc_proposals: list of dicts with lat, lon as keys
            (typically, OSM records)
        target_location: dict of form {loc_name: loc_data}
        max_dist: max accpetable distance form target_coords in km

    Returns: dict
    """
    if len(geoloc_proposals) == 0:
        return {}
    target_coords = get_coord_array(target_location)
    proposals_dists = []
    for gp in geoloc_proposals:
        lat, lon = float(gp['lat']), float(gp['lon'])
        dist = geopy.distance.great_circle((lat, lon), target_coords)
        proposals_dists.append((gp, dist.kilometers))
    proposals_dists.sort(key=lambda pd: pd[1])
    best_proposal, least_dist = proposals_dists[0]
    return best_proposal if least_dist <= max_dist else {}


# Utility to plot geoclusters

def cluster_plot(coord_clusters, output_filename, scaling=10):
    """Scatterplot clusters of lat/lon coords.

    Arguments:
        clusters: numpy array of shape (n,2)
        output_filename: text string (with image suffix, e.g. .png
            or .jpg, or if no suffix, default is .png)
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
    plt.savefig(output_filename, bbox_inches='tight') 
    return

