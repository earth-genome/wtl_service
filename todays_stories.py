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
    end = today + datetime.timedelta(days=1)
    start = today - datetime.timedelta(days=3)

    stories = news_scraper.STORY_SEEDS.grab_stories(
        category='/WTL',
        startDate=start.isoformat(),
        endDate=end.isoformat())

    cleaned = []
    for s in stories:
        try:
            d = {'title': s.record['title']}
            d.update({'url': s.record['url']})
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
