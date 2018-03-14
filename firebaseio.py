""" Routines to manage firebase database entries for stories, locations,
text.

Class DBItem: An element (item) of a firebase database.

    Attributes:
        category: firebase category (see GL_KNOWN_CATEGORIES)
        idx: index within the category
        record: dict holding data for the item

Class DB: Firebase database, with methods for manipulating
    DBItem instances, derived from the firebase.FirebaseApplication class.  

    Includes inherited methods put, post, get, delete
     (ref https://ozgur.github.io/python-firebase/)

"""

import re

from dateutil.parser import parse
from firebase.firebase import FirebaseApplication

FB_FORBIDDEN_CHARS = u'[.$\%\[\]#/?\n]'
BASE_CATEGORY = '/stories'

# In general data values will be strings, but for the following types,
# values are dicts of strings paired with relevance scores and/or geocoords
DICT_DATA_TYPES = ('image_tags', 'keywords', 'locations')

class DB(FirebaseApplication):
    """Firebase database. 

    Attributes:
        url: location of the firebase database

    Methods for manipulating DBItem instances:
        put_item
        check_known (if item is in database)
        grab_data (materials from specified subheading)
        grab_stories (all stories from a category)
        delete_item
        delete_category
        delete_all_mentions (of item from specified categories)
        
    """

    def __init__(self, database_url):
        FirebaseApplication.__init__(self, database_url, None)
        self.url = database_url
    
    def put_item(self, item):
        """
        Upload an item to databse. Returns the record if successful,
        otherwise None.
        """
        return self.put(item.category, item.idx, item.record)

    def check_known(self,item):
        if self.get(item.category, item.idx) is None:
            return False
        else:
            return True

    def grab_data(self, category=BASE_CATEGORY, data_type='text'):
        """Download specified materials from all stories in given category.

        Supported data_type can be 'text', 'keywords', 'image', or any
        other secondary heading in the database.

        Returns:  List of story indices and list of data.
        """
        raw = self.get(category, None)
        indices = list(raw.keys())
        data = []
        for v in raw.values():
            try: 
                data.append(v[data_type])
            except KeyError:
                if data_type in DICT_DATA_TYPES:
                    data.append({})
                else:
                    data.append('')
        return indices, data

    def grab_stories(self, category=BASE_CATEGORY):
        """Download all stories in a given category.

        Returns a list of DBItems.
        """
        raw = self.get(category, None)
        stories = [DBItem(category, idx, record) for idx, record in
                   raw.items()]
        return stories
                
    def delete_item(self,item):
        self.delete(item.category, item.idx)
        return

    def delete_category(self, category):
        self.delete(category, None)
        return

    def delete_all_mentions(self, idx, categories=[BASE_CATEGORY]):
        for c in categories:
            self.delete(c, idx)
        return

class DBItem(object):
    """Creates a firebase database item.

    Attributes:
        category: firebase category (see GL_KNOWN_CATEGORIES)
        idx: index within the category
        record: dict holding data for the item

    """

    def __init__(self, category, idx=None, record=None):

        if idx is None and record is None:
            raise ValueError
        self.category = category
        self.record = record
        if idx is None:
            self.idx = self.make_idx()
        else:
            self.idx = idx

    def make_idx(self, max_len=96):
        """Construct an index for a database item.

        Generically, idx is based on title. Lacking title, the url is
        substituted.

        Returns: a unicode string.
        """
        try:
            idx = self.record['title']
        except KeyError:
            try:
                idx = record['url']
            except KeyError:               
                raise
        idx = re.sub(FB_FORBIDDEN_CHARS,'',idx)
        return idx[:max_len]
    
