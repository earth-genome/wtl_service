from flask import Flask, render_template, json, request
import firebase
import random

app = Flask(__name__)


FIREBASE_URL = 'https://newsy-bfbd4.firebaseio.com'
fb = firebase.FirebaseApplication(FIREBASE_URL, None)


def check_geo(article):
    ks = article.keys()
    if 'locations' in ks:

        geos = []
        for loc in article['locations']:
            geos.append('geo' in loc.keys())

        return any(geos)

    else:
        return False


DATA = fb.get("/", None)
geo_articles = [article for article in DATA['reuters'].values() if check_geo(article)]


@app.route('/classify')
def classify():

    [article] = random.sample(geo_articles, 1)

    sample_data = {
        'outlet': 'reuters',
        'title': article['title'],
        'url': article['url'],
        'publishedAt': article['publishedAt'],
        'description': article['description'],
        'locations': article['locations']
    }

    return render_template('classify.html', data=sample_data)


if __name__ == "__main__":
    app.run(port=5000)
