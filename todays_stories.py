"""Wrapper to dump current story titles and their core_locations to json.

Usage: python todays_stories.py

Output: json file

Notes:  Date range is two days ago through tomorrow; only stories with
core_locations are included.
"""

import datetime
import json
import sys

import news_scraper


if __name__ == '__main__':

    try: 
        daysback = int(sys.argv[1])
    except:
        daysback = int(input('How many days back to grab stories?' +
                             ' Recommended 1, 2, or 3: '))
            
    today = datetime.date.today()
    end = today + datetime.timedelta(days=1)
    start = today - datetime.timedelta(days=daysback)

    stories = news_scraper.STORY_SEEDS.grab_stories(
        category='/WTL',
        startDate=start.isoformat(),
        endDate=end.isoformat())

    cleaned = []
    for s in stories:
        try:
            d = {'title': s.record['title']}
            d.update({'url': s.record['url']})
            if 'themes' in s.record.keys():
                d.update({'themes': s.record['themes']})
            else:
                d.update({'themes': {}})
            d.update({
                'locations': {
                    k:(v['lat'], v['lon']) for k,v
                    in s.record['core_locations'].items()
                }
            })
            cleaned.append(d)
        except:
            pass

with open('../WTLs/WTL{}.json'.format(today), 'w') as f:
    json.dump(cleaned, f, indent=4)
