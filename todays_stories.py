"""Wrapper to dump current story titles and their core_locations to json.

Usage: python todays_stories.py

Output: json file

Notes:  Date range is two days ago through tomorrow; only stories with
core_locations are included.
"""

import datetime
import json

import news_scraper


if __name__ == '__main__':
    
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)
    twoago = today - datetime.timedelta(days=2)

    stories = news_scraper.STORY_SEEDS.grab_stories(
        category='/WTL',
        startDate=twoago.isoformat(),
        endDate=tomorrow.isoformat())

    cleaned = []
    for s in stories:
        try:
            d = {'title': s.record['title']}
            d.update({
                'locations': {
                    k:v['boundingbox'] for k,v
                    in s.record['core_locations'].items()
                }
            })
            cleaned.append(d)
        except:
            pass

with open('WTL{}.json'.format(today), 'w') as f:
    json.dump(cleaned, f, indent=4)
