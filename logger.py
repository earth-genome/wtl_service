"""Logging utilties."""

import datetime
import json
import os

def log_exceptions(log, directory):
    """Write exceptions to file."""
    if log == '':
        return
    if not os.path.exists(directory):
        os.makedirs(directory)
    logfile = os.path.join(directory,
                           datetime.date.today().isoformat()+'.log')
    with open(logfile, 'a') as f:
        f.write(log)
    return

# deprecated:
def log_feed(feed, directory):
    """Write feed to json file."""
    if feed == {}:
        return
    if not os.path.exists(directory):
        os.makedirs(directory)
    feedfile = os.path.join(directory,
                            datetime.datetime.now().isoformat()+'.json')
    with open(feedfile, 'a') as f:
        json.dump(feed, f, indent=4)
    return
