""" Routines to manage texts associated to Firebase stories for training
 and running a classifier.

External functions:
    grab():  Download texts from a Firebase database.
    upload():  For stories already in a Firebase database that satisfy
        specified date parameters, upload their texts to the database.
    clear_all():  Remove all texts from a database.

"""
from datetime import date
import sys

# TODO: better module handling
sys.path.append('../')
import config
import firebaseio
import story_maker

# our firebase databases
GOOD_LOCATIONS = firebaseio.DB(config.FIREBASE_GL_URL)
NEGATIVE_TRAINING_CASES = firebaseio.DB(config.FIREBASE_NEG_URL)
STORY_SEEDS = firebaseio.DB(config.FIREBASE_URL)

def grab(database):
    """Download texts from a Firebase database."""
    texts_dict = database.get('/texts', None)
    texts = [' '.join(chunks) for chunks in texts_dict.values()]
    return list(texts_dict.keys()), texts

def upload(database,
            start_date=date.today().isoformat(),
            end_date=None,
            from_category='/stories'):
    """Given stories in Firebase and a date range, upload their texts to
    Firebase.

    For running a classifier we may find it convenient first to 
    (temporarily) batch upload texts for stories fitting certain
    parameters.  Presumably this is to be followed later by clear_all().

    Date arguments can be isoformat dates or (preferably) datetimes.
    """
    stories = database.get(from_category, None)
    
    def build_date_filter(start_date, end_date):
        """Build a function to make a one- or two-sided comparison
        of date against start_date and/or end_date.

        Returns: function date_filter, which returns a bool
        """
        def date_filter(date):
            if start_date is None and end_date is None:
                return True
            elif start_date is None:
                return True if date < end_date else False
            elif end_date is None:
                return True if date > start_date else False
            else:
                if (date > start_date and date < end_date):
                    return True
                else:
                    return False
        return date_filter
    
    date_filter = build_date_filter(start_date, end_date)
    for name, metadata in stories.items():
        try: 
            if date_filter(metadata['date']):
                story = firebaseio.DBItem(from_category, name, metadata) 
                text = story_maker.new_text(story)
                database.put_item(text)
        except KeyError:
            pass
    return

def clear_all(database, category='/texts'):
    """Remove all texts from database."""
    database.delete_category(category)
