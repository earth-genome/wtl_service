# Processes all stories for english language outlets on newsapi.org at the
# time when the script is called.  The objective is to call this script
# multiple times each day.

import requests
from story import newStory
from config import NEWS_API_KEY

OUTLETS = [
	"time",
	"bloomberg",
	"the-washington-post",
	"the-new-york-times",
	"reuters",
	"national-geographic",
	"hacker-news",
	"newsweek",
	"mirror",
	"mtv-news",
	"google-news",
	"mashable",
	"polygon",
	"techcrunch",
	"the-economist",
	"the-next-web",
	"fortune",
	"associated-press",
	"financial-times",
	"recode",
	"techradar",
	"the-huffington-post",
	"the-verge",
	"metro",
	"business-insider-uk",
	"cnbc",
	"cnn",
	"daily-mail",
	"engadget",
	"focus",
	"reddit-r-all",
	"the-hindu",
	"the-times-of-india",
	"usa-today"
]

def process():
	
	for outlet in OUTLETS:

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

				print s.url
				
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


