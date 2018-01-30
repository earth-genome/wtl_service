# extracts and chunks text from a web page into cleaned and manageable bites.
import requests
import html2text
from bs4 import BeautifulSoup

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


def chunk_text(text, N=8, chunk_size=800):
	# Accepts a large string.  Returns a list of `N` chunks, each with
	# `chunk_size` words.  
	text = BeautifulSoup(text).text.encode('UTF-8')
	words = text.split()
	words = [str(x) for x in words]

	def _chunks(l, n):
	    # Yield successive n-sized chunks from l.
	    for i in range(0, len(l), n):
	        yield l[i:i + n]

	return [' '.join(t) for t in _chunks(words, chunk_size)][0:N]


def get_text(url):
	html_text = requests.get(url).text
	text = process_html(html_text)
	return chunk_text(text)