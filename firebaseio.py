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

import firebase
import re
import datetime
from dateutil.parser import parse


FB_FORBIDDEN_CHARS = u'[.$\[\]#/]'
KNOWN_GL_CATEGORIES = [
    '/stories',
    '/satellite_stories',
    '/locations',
    '/texts'
    ]

class DB(firebase.FirebaseApplication):
    """Firebase database. 

    Attributes:
        url: location of the firebase database

    Methods for manipulating DBItem instances:
        put_item
        check_known
        get_item
        find_item
        delete_item
        delete_category
        
    """

    def __init__(self,database_url):
        firebase.FirebaseApplication.__init__(self,database_url, None)
        self.url = database_url
    
    def put_item(self,item):
        """
        Upload an item to databse. Returns the record if successful,
        otherwise None.
        """
        return self.put(item.category,item.idx,item.record)

    def check_known(self,item):
        if self.get(item.category,item.idx) is None:
            return False
        else:
            return True

    # TODO: Improve search functionality. As far as I can tell
    # the firebase query functionality does not exist in the python api.
    # Achtung! This will possibly touch every item in the database.
    def find_item(self,idx):
        item = None
        for c in KNOWN_GL_CATEGORIES:
            items = self.get(c,None)
            if items is not None:
                try:
                    record = items[idx]
                    item = DBItem(c,idx,record)
                except KeyError:
                    pass
        return item
                
    def delete_item(self,item):
        self.delete(item.category,item.idx)

    def delete_category(self,category):
        self.delete(category,None)

    def delete_all_mentions(self,idx):
        for c in KNOWN_GL_CATEGORIES:
            self.delete(c,idx)

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
        """Construct an index for a database item from date/time and title.

        If date/time are not available, the time of generation
        (noted by '-gen') is substituted.  Title may be null.

        Returns: a unicode string.
        """
        try:
            date = parse(self.record['date']).isoformat()
        except KeyError:
            date = datetime.datetime.utcnow().isoformat()
            date = date.split('.')[0] + 'Z-gen'
        try:
            title = self.record['title']
        except KeyError:
            title = ''
        idx = date + ' ' + title
        idx = re.sub(FB_FORBIDDEN_CHARS,'',idx)
        return idx[:max_len]
    
