"""Simple operations to build and maintain a Redis database of recently
scraped urls. For use within news_scraper.py.
"""

import datetime
import os

import redis

# Heroku provides the env variable REDIS_URL for Heroku redis;
# the default redis://redis_db:6379 points to the local docker redis
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis_db:6379')

class TrackURLs(object):
    """Class to track scraped urls in a Redis database.

    URLs are stored as a sorted set. An element of the set is a url paired
        with the timestamp when it was added to the database.
        
    Attributes:
        set: The name of the sorted set
        staleafter: Number of days after which stored urls are purged
        conn: Instantiated connection to the redis database

    Methods:
        find_fresh: Determine which among input urls are not yet in the
            database.
        add: Add element to database.
        purge: Remove elements older than timestamp.
    """
        
    def __init__(self, set_name='urls', staleafter=7, redis_url=REDIS_URL):
        self.set = set_name
        self.staleafter = staleafter
        self.conn = redis.from_url(redis_url, decode_responses=True)

        awhileago = (datetime.datetime.now() - datetime.timedelta(
            days=self.staleafter)).timestamp()
        self.purge(awhileago)

    def find_fresh(self, urls):
        """Determine which among input urls are not yet in the database."""
        existing = self.conn.zrange(self.set, 0, self.conn.zcard(self.set))
        fresh = set(urls).difference(existing)
        print('{} news stories harvested.'.format(len(fresh)))
        return fresh
        
    def add(self, url, timestamp):
        """Add element to database."""
        return self.conn.zadd(self.set, **{url:timestamp})

    def purge(self, timestamp):
        """Remove elements older than timestamp."""
        num_deleted = self.conn.zremrangebyscore(self.set, 0, timestamp)
        print('Redis: Purged {} urls stale by {} days'.format(
            num_deleted, self.staleafter))
        return num_deleted
