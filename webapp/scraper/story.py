# Create story objects to better handle the processing and storing of news
# stories

import hashlib
import firebase
import geolocate
import requests

from config import FIREBASE_URL

fb = firebase.FirebaseApplication(FIREBASE_URL, None)

class newStory:

    def __init__(self, title, outlet, publishedAt, description, url):
        
        self.title = title
        self.outlet = outlet
        self.date = publishedAt
        self.description = description
        self.url = url

        # Create a unique hash based on outlet, date, and title to be the
        # index within the firebase table
        m = hashlib.md5()
        m.update(str([outlet, publishedAt, title]))
        self.idx = str(int(m.hexdigest(), 16))

        self.meta = {
			"title": self.title,
			"outlet": self.outlet,
			"date": self.date,
			"description": self.description,
            "url": self.url
		}


    def check_uploaded(self):
        if (fb.get("/raw_no_geo", self.idx) is None) and (fb.get("/raw_geo", self.idx) is None):
            return False
        else:
            return True


    def post_raw(self):

        # Geolocate the facilities mentioned in the linked text of the article
        try:
            html_text = requests.get(self.url).text
            text = geolocate.process_html(html_text)
            self.locations = geolocate.facilitize(text)
        except:
            self.locations = {}

        # Create a boolean to note whether the story has been successfully
        # geolocated
        if any(self.locations):
            self.geolocated = True
            self.meta["locations"] = self.locations
        else:
            self.geolocated = False


        record = {
			"meta": self.meta,
        	"vetted": False,
        	"geolocated": self.geolocated
        }

        print(record)

        if self.geolocated == True:
            fb.put("/raw_geo", self.idx, record)
        else:
            fb.put("/raw_no_geo", self.idx, record)

