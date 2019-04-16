"""Wrapper to dump current story titles and their core_locations to json.

Usage: python todays_stories.py

Output: json file

Notes:  Date range is two days ago through tomorrow; only stories with
core_locations are included.
"""

import datetime
import json
import sys

from utilities import firebaseio

if __name__ == '__main__':

    try: 
        daysback = int(sys.argv[1])
    except:
        daysback = int(input('How many days back to grab stories?' +
                             ' Recommended 1, 2, or 3: '))
            
    today = datetime.date.today()
    end = today + datetime.timedelta(days=1)
    start = today - datetime.timedelta(days=daysback)

    stories = firebaseio.DB('story-seeds').grab_stories(
        category='/WTL',
        orderBy='scrape_date',
        startAt=start.isoformat(),
        endAt=end.isoformat())

    cleaned = []
    for s in stories:
        c = {k:s.record.get(k) for k in
                 ['title', 'url', 'themes', 'core_location']}
        cleaned.append(c)
            
with open('../WTLs/WTL{}.json'.format(today), 'w') as f:
    json.dump(cleaned, f, indent=4)
