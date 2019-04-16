"""Routines to retrieve URLs from wire services."""

import datetime
import random
import os

from google.cloud import bigquery
import requests

WIRE_URLS = {
    'newsapi': 'https://newsapi.org/v2/everything',
    'gdelt': 'https://gdelt-seeds.herokuapp.com/urls'
}

OUTLETS_FILE = 'newsapi_outlets.txt'

def newsapi():
    """"Retrieve urls and metadata from the NewsAPI service."""
    with open(OUTLETS_FILE,'r') as f:
        outlets = [line.strip() for line in f]
    random.shuffle(outlets)

    records = []
    for outlet in outlets:
        payload = {
            'sources': outlet,
            'from': datetime.date.today().isoformat(),
            'apiKey': os.environ['NEWS_API_KEY']
        }
        try:
            data = requests.get(WIRE_URLS['newsapi'], params=payload)
            articles = data.json()['articles']
        except Exception:
            continue
        for article in articles:
            metadata = {k:v for k,v in article.items() if k in
                        ('url', 'title', 'description')}
            if 'publishedAt' in article:
                metadata.update({
                    'publication_date': article['publishedAt']
                })
            records.append(metadata)
    return records

def gdelt():
    """Retrieve urls and metadata from the GDELT service."""
    client = bigquery.Client()
    
    date_data = client.query('SELECT max(SQLDATE) as sqldate '
        'FROM `gdelt-bq.full.events`').to_dataframe()
    date = date_data.sqldate[0]

    df = client.query('SELECT SOURCEURL FROM `gdelt-bq.full.events` '
        'WHERE SQLDATE = %s' % date).to_dataframe()
    df = df.drop_duplicates(subset='SOURCEURL', keep='last')
    df = df.sample(frac=1)
    df.rename(columns={'SOURCEURL':'url'}, inplace=True)
    return df.to_dict(orient='records')


