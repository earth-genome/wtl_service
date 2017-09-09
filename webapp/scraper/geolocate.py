# Set of supporting functions to convert a chunk of text into the extracted
# locations and their geographic coordinates

import re 
import requests
import html2text

import watson_developer_cloud as wdc
import watson_developer_cloud.natural_language_understanding.features.v1 as features

from bs4 import BeautifulSoup
from firebase import firebase

from config import GOOGLE_GEO_API_KEY, WATSON_USER, WATSON_PASS

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
	'Club Metro',
	"Jamia Masjid",
	"Atlantic Ocean",
	"Florida Turnpike",
	"French island",
	"Target store",
	"Caribbean Sea",
	"The Home Depot",
	"Beach Plaza",
	"Tokyo Station",
	"Hang Seng Index",
	"Asia Pacific",
	"Abhimanyu Ghoshal",
	"Limited Quay House",
	"Project Runway",
	"National Geographic",
	"Abu Dhabi",
	"Princess Juliana St Maarten Airport",
	"Maho beach",
	"Atlantic Ocean",
	"Beach Plaza",
	"British Virgin Island Tortola",
	"New York Fashion",
	"Toronto Film Festival",
	"New York",
	"Monaco Grand Prix"
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
	# Accepts a text query and returns the lat-long coordinates.  Only the
	# first result is returned, if multiple are found.

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
	# Accepts a large chunk of text and returns the first N number of chunks
	# of words.
	text = BeautifulSoup(text).text.encode('UTF-8')
	words = text.split()
	words = [str(x) for x in words]

	def _chunks(l, n):
	    # Yield successive n-sized chunks from l.
	    for i in range(0, len(l), n):
	        yield l[i:i + n]

	return [' '.join(t) for t in _chunks(words, 800)][0:N]


def facilitize(text):
	"""Returns concepts associated with the text"""
	flavor = 'text/TextGetRankedNamedEntities'
	url = 'http://access.alchemyapi.com/calls/' + flavor
	chunks = chunk_text(text)

	res = {}

	for chunk in chunks:

		entities = entity_extraction(chunk)

		for entity in entities:

			if entity['type'] in ['Facility', 'GeographicFeature']:

				if entity['text'] not in bad_list:

					coords = geocode(entity['text'])
					if coords is not None:
						cleaned = {
								'relevance': entity['relevance'],
								'coords': coords
							}

						res[entity['text']] = cleaned
						print(entity['text'])
						print(cleaned)

	return res


def process_html(html):
	# Accepts HTML and returns the text therein.
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


