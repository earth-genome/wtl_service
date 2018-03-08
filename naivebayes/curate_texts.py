"""Routines to manage texts associated to Firebase stories for training
 and running a classifier.  (Currently deprecated.)

External functions:
    grab():  Download texts from a Firebase database.
    upload():  For stories already in a Firebase database that satisfy
        specified date parameters, upload their texts to the database.
    clear_all():  Remove all texts from a database.

"""
from datetime import date
import re
import sys

sys.path.append('../')
import extract_text

def upload(database,
            start_date=date.today().isoformat(),
            end_date=None,
            to_category='/texts',
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
    for name, record in stories.items():
        try: 
            if date_filter(record['publication_date']):
                text = extract_text.get_text(record['url'])[0]
                record.update({'text': text})
                text_item = firebaseio.DBItem(to_category, name, record) 
                database.put_item(text_item)
        except KeyError:
            pass
    return

def clear_all(database, category='/texts'):
    """Remove all texts from database."""
    database.delete_category(category)
