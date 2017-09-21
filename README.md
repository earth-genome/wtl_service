# news-scrape

### Developing locally

```bash
python app.py
```

Better to use `docker-compose` to get closer to the production environment - particularly for the web app:

```shell
docker-compose up --build
```

Run tests using `pytest`:

```shell
# mount a volume with the code in it
docker run -v /path/to/news-scrape:/code/ -it newsscrape_web /bin/sh
# now you're inside the container
$ pytest

    def test_news_api_key():
>       assert type(config.NEWS_API_KEY) == 'str'
E       AssertionError: assert <type 'str'> == 'str'
E        +  where <type 'str'> = type('eb53420a213b46e8be51d89f18e87e11')
E        +    where 'eb53420a213b46e8be51d89f18e87e11' = config.NEWS_API_KEY

Scrape/scrape/test/config_test.py:5: AssertionError
```