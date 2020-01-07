"""Routines to manage Firebase story databases.

Class DBItem: Container for a story in a Firebase database.

Class DBClient: Firebase database client derived from the 
    firebase.FirebaseApplication class, with methods for uploading and
    retrieving DBItem instances. Includes inherited methods put, post, 
    get, and delete. (Ref: https://ozgur.github.io/python-firebase/)

Class DB: Descendant class to quickly instantiate DBClient on one of the 
    known FIREBASES listed below.

Usage, e.g. to pull recent stories from the where-to-look (story-seeds) 
database:
> seeds = DB('story-seeds')
> stories = seeds.grab_stories('/WTL', orderBy='scrape_date', 
                               startAt='2019-04-15', endAt='2019-04-17')

"""

import os
import re

from firebase import firebase

# Our databases. 
FIREBASES = {
    'story-seeds': 'https://overview-seeds.firebaseio.com',
    'good-locations': 'https://good-locations.firebaseio.com',
    'negative-training-cases': 'https://negative-training-cases.firebaseio.com/'
}

# Auth keys should be held in these environment variables.
AUTH_KEY_ENV_VARS = {
    'story-seeds': 'FIREBASE_SECRET_SEEDS',
    'good-locations': 'FIREBASE_SECRET_GL',
    'negative-training-cases': 'FIREBASE_SECRET_NEG'
}

FB_FORBIDDEN_CHARS = u'[.$\%\[\]#/?\n]'

# Server-side date filtering/ordering can be enabled via rules set in the
# Firebase console.  They must be set for each top-level key separately.
# E.g. for category '/stories' you would add the rules:
# "stories": {".indexOn": ["publication_date", "scrape_date"]}
# Having done so for all three databases, we have then:
ALLOWED_ORDERINGS = ['scrape_date', 'publication_date']

# Firebase deletes keys with empty dicts as values.  For classification,
# we need the empty data record.
EMPTY_DATA_VALUES = {
    'description': '',
    'image': '',
    'image_tags': {},
    'keywords': {},
    'locations': {},
    'outlet': '',
    'probability': 0.,
    'publication_date': '',
    'text': '',
    'title': '',
    'url': ''
}

class DBClient(firebase.FirebaseApplication):
    """Firebase database client. 

    Descendant attribute:
        url: URL for the Firebase database

    Descendant methods:
        put_item: Upload an item to the database.
        check_known: Check whether an item exists in the database.
        delete_item: Delete an item from the database.
        delete_category: Delete a top-level key and all its records from the 
            database.
        grab_stories: Download items in a given category.
        grab_data: Download item components of a specific data_type.
        
    """
    def __init__(self, url, secret):
        if secret:
            auth = firebase.FirebaseAuthentication(secret, '', admin=True)
        else:
            auth = None
        super().__init__(url, authentication=auth)
        self.url = url
    
    def put_item(self, item, verbose=False):
        """Upload an item to database. 

        Arguments:
            item: A DBItem story.
            verbose: If true, the server will return the item record on 
                success - useful for verification but expensive in data 
                transfer. If false, the server gives a null response regardless.

        Returns: None, or the record if successful and verbose=True
        """
        params = {'print': 'pretty'} if verbose else {'print': 'silent'}
        return self.put(item.category, item.idx, item.record, params=params)

    def check_known(self, item):
        """Check whether an item exists in the database."""
        return True if self.get(item.category, item.idx) else False

    def delete_item(self,item):
        """Delete an item from the database."""
        self.delete(item.category, item.idx)

    def delete_category(self, category):
        """Delete a top-level key and all its records from the database.

        Note: This method requires confirmation from the user in an interactive
            session.
        """
        warning = ('Warning. All data in {} '.format(category) +
                   'will be permanently deleted. Continue (y/n)? ')
        conf = input(warning)
        if conf.strip() == 'y':
            self.delete(category, None)
        else:
            print('Exiting. No category deleted.')

    def grab_stories(self, category, orderBy=None, **dates):
        """Download items in a given category.

        Arguments:
            category: database top-level key
            orderBy: one of the above ALLOWED_ORDERINGS
            optional dates: startAt/endAt: isoformat date or datetime to
                filter ordering

        Returns a list of DBItems.
        """
        params = self._format_ordering_params(orderBy, **dates)
        raw = self.get(category, None, params=params)
        stories = [DBItem(category, idx, record) for idx, record in raw.items()]
        return stories

    def grab_data(self, category, data_type, orderBy=None, **dates):
        """Download item components of a specific data_type.

        Arguments:
            category: database top-level key
            data_type: can be 'text', 'keywords', 'image', or any
                secondary heading listed in EMPTY_DATA_VALUES.
            orderBy: one of the above ALLOWED_ORDERINGS
            optional dates: startAt/endAt: isoformat date or datetime to
                filter ordering

        Returns: List of story indices and list of data.
        """
        params = self._format_ordering_params(orderBy, **dates)
        raw = self.get(category, None, params=params)
        indices = list(raw.keys())
        data = []
        for v in raw.values():
            try: 
                data.append(v[data_type])
            except KeyError:
                try:
                    data.append(EMPTY_DATA_VALUES[data_type])
                except KeyError as e:
                    raise KeyError('Firebaseio: No EMPTY_DATA_VALUE assigned: '
                                   '{}'.format(repr(e)))
        return indices, data

    def _format_ordering_params(self, orderBy, **dates):
        if not orderBy:
            return {}
        elif orderBy not in ALLOWED_ORDERINGS:
            raise ValueError('orderBy must be one of {}'.format(
                ALLOWED_ORDERINGS))
        else:
            params = {'orderBy': '"{}"'.format(orderBy)}
            params.update({k: '"{}"'.format(v) for k,v in dates.items()})
            return params

class DB(DBClient):
    """Firebase database client for named databases."""
    def __init__(self, database_name):
        super().__init__(FIREBASES[database_name],
                         os.environ[AUTH_KEY_ENV_VARS[database_name]])
        self.name = database_name
    
class DBItem(object):
    """Container for a Firebase database story.

    Attributes:
        category: database top-level key
        idx: index within the category
        record: dict holding data for the item. 
    """
    def __init__(self, category, idx, record):
        self.category = category
        self.record = record
        self.idx = idx if idx else self._make_idx()

    def _make_idx(self, max_len=96):
        """Construct an index for a database item.

        The idx is based on title if available, or url.
        """
        idx = self.record.get('title')
        if not idx:
            try:
                idx = self.record['url']
            except KeyError:
                raise KeyError('A title or url is required.')
        idx = re.sub(FB_FORBIDDEN_CHARS,'',idx)
        return idx[:max_len]
    
