"""Apply geolocation model to backqueried stories to choose core location
   Usage:
   > pin = GeoPin()
   > pin(story_record)"""

import joblib
import numpy as np

import pyproj
import shapely.geometry

# MODEL = joblib.load('../saved_models/geoloc_model/geoloc_model200229.pkl')

class GeoPin(object):
    
    def __init__(self, model):
        self.model = model
        
    def __call__(self, story):
        locations = story.get('locations')
        if locations:
            core = self.evaluate(locations)
            story.update({'core_location': core})
        
    def evaluate(self, choices):
        """Choices: dictionary of story locations in format
            {location: {dict_of_data}}"""
        for choice in choices.values():
            quants = prep_quants(choice)
            [prediction] = self.model.predict(quants)
            choice.update({'map_relevance': prediction})
        by_relevance = sorted(choices.values(), key=lambda l: l['map_relevance'])
        return by_relevance[0]

def prep_quants(data):
    """Extract quantitative features from location data."""
    quants = [
        data.get('relevance', 0),
        len(data.get('mentions', [])),
        len(data.get('cluster', [])),
        data.get('cluster_ratio', 0)
    ]
    bounds = data.get('boundingbox', ())
    if bounds:
        quants.append(np.sqrt(_compute_area(bounds)))
    else:
        quants.append(0.0)
    return np.array(quants).reshape(1, -1)

def _compute_area(bounds):
    """Compute the area of geographic bounds.

    Argument bounds: decimal lat/lon coordinates in order
        (lower_left_lon, lower_left_lat, upper_right_lon, upper_right_lat)

    Returns: Area in km^2.
    """
    SQm_to_SQkm = 1e-6
    epsg_code = _get_utm_code(*bounds[:2])
    projector = pyproj.Proj(init='epsg:{}'.format(epsg_code))
    lowerleft = projector(*bounds[:2])
    upperright = projector(*bounds[2:])
    bbox = shapely.geometry.box(*lowerleft, *upperright)
    return bbox.area * SQm_to_SQkm
    
def _get_utm_code(lon, lat):
    """Compute the UTM EPSG zone code in which lon, lat fall."""
    basecode = 32601 if lat > 0 else 32701
    return basecode + int((180 + lon)/6.)
