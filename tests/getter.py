import main
import requests

DATA = main.fb.get("/", None)


def get_names(data):
	source_idx = DATA.keys()

	sources = requests.get("https://newsapi.org/v1/sources").json()

	n_stories = 0
	for source in sources:

		if source['id'] in source_idx:
			stories = DATA[source['id']]

			n_stories = n_stories + len(stories)



def total():
	return sum([len(DATA[x].keys()) for x in DATA.keys()])


def check_geo(article):
	ks = article.keys()
	if 'locations' in ks:

		geos = []
		for loc in article['locations']:
			geos.append('geo' in loc.keys())

		return any(geos)

	else:
		return False


def total_geo():
	source_geo = []

	for source in DATA.keys():
		x = [check_geo(article) for article in DATA[source].values()]
		source_geo.append(sum(x))

	return sum(source_geo)


def counter():
	x = total()
	y = total_geo()
	z = int(float(y)/x * 100)

	print("\nThere are %s articles in the database." % x)
	print("There are %s with geocoded facilities or features." % y)
	print("This accounts for %s percent of stories.\n" % z)
