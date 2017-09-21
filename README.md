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
================= test session starts ========================
platform linux2 -- Python 2.7.12, pytest-3.2.2, py-1.4.34, pluggy-0.4.0
rootdir: /code, inifile:
collected 2 items

Scrape/scrape/test/config_test.py ..

============== 2 passed in 0.12 seconds ======================
```