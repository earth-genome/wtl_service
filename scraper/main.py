# Processes all stories for english language outlets on newsapi.org at the
# time when the script is called.  The objective is to call this script
# multiple times each day.

import requests
from story import newStory
from config import NEWS_API_KEY


def process():
	
	base_url = 'https://newsapi.org/v1/sources'
	data = requests.get(base_url, params={'language': 'en'})
	outlets = [x['id'] for x in data.json()['sources']]	
	
	for outlet in outlets:

		# TODO: Figure out if calling "top" vs. "latest" gets us more than 10
		# stories at a time for each outlet

		print("\n%s\n" % outlet)
		base_url = 'https://newsapi.org/v1/articles'
		payload = {
			'source': outlet,
			'apiKey': NEWS_API_KEY
		}

		data = requests.get(base_url, params=payload)
		articles = data.json()['articles']

		for article in articles: 

			try:

				s = newStory(
					title=article['title'],
					outlet=outlet,
					publishedAt=article['publishedAt'],
					description=article['description'],
					url=article['url']
				)

				if s.check_uploaded():
					pass
				else:
					s.post_raw()

			except Exception, e:
				# TODO: check exceptions.  Try to handle and fix in a better
				# way, e.g., '400 Client Error: Bad Request for url'
				print(e)

	print("complete")
	return True

if __name__ == "__main__":
	x = process()


