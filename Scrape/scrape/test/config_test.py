from scrape import config


def test_news_api_key():
    assert config.NEWS_API_KEY[0] == 'e'


def func(x):
    return x + 1


def test_answer():
    assert func(3) == 4
