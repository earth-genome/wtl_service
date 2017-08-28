import re 
import json
import requests
import html2text

import watson_developer_cloud as wdc
import watson_developer_cloud.natural_language_understanding.features.v1 as features

from bs4 import BeautifulSoup
from firebase import firebase


ALCHEMY_API_KEY = 'a9656b5adaccb210817045db9cbb5462bbd26f3c'
NEWS_API = 'eb53420a213b46e8be51d89f18e87e11'
GOOGLE_GEO_API_KEY = 'AIzaSyD7juQAE6OZhwLI_2Dwz7k9s5VUv032U_c'
FIREBASE_URL = 'https://newsy-bfbd4.firebaseio.com'

WATSON_USER = "66b08509-e65c-4e2e-b400-3b509d35486c"
WATSON_PASS = "d7LMDaQ61MDm"

fb = firebase.FirebaseApplication(FIREBASE_URL, None)

bad_list = [
	'Art & Design',
	'White House',
	'Fine Art',
	'Cambridge Cyber Summit',
	'Trump Tower',
	'Bloomberg Terminal',
	'Trump White House',
	'East Room',
	'East Wing',
	'Rex Tillerson',
	'Atlantic',
	'The White House',
	'Oval Office',
	'La La Land',
	'Bay Area',
	'Great Lakes',
	'Silicon Valley',
	'Bush White House',
	'Earth Mother Nature Network',
	'City Hall',
	'D.C. Sports Bog',
	'Cape Up',
	'AL Central',
	'Copa Am\xe9rica',
	'Purple Rain',
	'Full Circle Cafe',
	'Save Jewish Heritage',
	'Town Hall',
	'West Coast',
	'Arts Home',
	'Help Centre',
	'Holland Park',
	'Club Metro'
]


def entity_extraction(text):

	nlu = wdc.NaturalLanguageUnderstandingV1(
		version='2017-02-27',
		username=WATSON_USER,
		password=WATSON_PASS
	)

	x = nlu.analyze(
		text=text,
		features=[features.Entities()]
	)

	return x['entities']



def geocode(text):
	"""

	Accepts a text query and returns the lat-long coordinates.  Only the first
	result is returned, if multiple are found.
	
	"""
	base = 'https://maps.googleapis.com/maps/api/place/textsearch/json'

	payload = {
		'query': text,
		'key': GOOGLE_GEO_API_KEY
	}

	data = requests.get(base, params=payload).json()

	if data['status'] == 'OK':
		return data['results'][0]['geometry']['location']
	elif data['status'] == 'ZERO_RESULTS':
		return None
	elif data['status'] == 'INVALID_REQUEST':
		return None
	else:
		raise Exception('Geocode error: %s' % data['status'])


def create_idx(string_title, n=70):
	title = re.sub(r'([^\s\w]|_)+', '', string_title)
	return title[0:n]

def chunk_text(text, N=5):
	"""
	
	Accepts a large chunk of text and returns the first N number of chunks of
	words.

	"""
	text = BeautifulSoup(text).text.encode('UTF-8')
	words = text.split()
	words = [str(x) for x in words]

	def _chunks(l, n):
	    """Yield successive n-sized chunks from l."""
	    for i in range(0, len(l), n):
	        yield l[i:i + n]

	return [' '.join(t) for t in _chunks(words, 800)][0:N]


def facilitize(text):
	"""Returns concepts associated with the text"""
	flavor = 'text/TextGetRankedNamedEntities'
	url = 'http://access.alchemyapi.com/calls/' + flavor
	chunks = chunk_text(text)

	res = []

	for chunk in chunks:

		entities = entity_extraction(chunk)

		for entity in entities:

			if entity['type'] in ['Facility', 'GeographicFeature']:
			
				cleaned = {
					'type': entity['type'],
					'text': entity['text'],
					'relevance': entity['relevance']
				}

				existing_entities = sum([list(x.values()) for x in res], [])
			
				if cleaned['text'] not in existing_entities:
					if cleaned['text'] not in bad_list:
						cleaned['geo'] = geocode(cleaned['text'])
						print(cleaned)
						res.append(cleaned)

	return res


def _process_html(html):
	"""

	Accepts HTML and returns the text therein.

	"""
	text_maker = html2text.HTML2Text()
	text_maker.ignore_links = True
	text_maker.bypass_tables = True
	text_maker.unicode_snob = False
	text_maker.decode_errors = 'ignore'
	text_maker.ignore_links = True
	text_maker.ignore_anchors = True
	text_maker.ignore_images = True
	text_maker.re_unescape = True
	text_maker.skip_internal_links = True

	return text_maker.handle(html)


def process_article(article):

	article_res = {
		'title': article['title'],
		'description': article['description'],
		'publishedAt': article['publishedAt'],
		'url': article['url']
	}

	try:

		html = requests.get(article['url']).text
		text = _process_html(html)
		article_res['locations'] = facilitize(text)

		return article_res

	except Exception as e:
		print(e)
		return  article_res


def process_outlet(outlet='bloomberg'):

	print("\n%s\n" % outlet)
	base_url = 'https://newsapi.org/v1/articles'
	payload = {
		'source': outlet,
		'apiKey': NEWS_API
	}

	data = requests.get(base_url, params=payload)
	articles = data.json()['articles']

	all_stories = fb.get("/", None)
	try:
		already_processed = all_stories[outlet].keys()
	except (TypeError, KeyError) as e:
		already_processed = []

	print("\n%s\n" % len(already_processed))

	for article in articles:
		idx = create_idx(article['title'])

		if idx not in already_processed:
			data = process_article(article)
			print(data['title'])
			try:
				fb.put("/" + outlet, idx, data)
			except Exception:
				pass

	total = fb.get("/" + outlet, None)
	return total


def process():

	sources = [
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

	return [process_outlet(source) for source in sources]

