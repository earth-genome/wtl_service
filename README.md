# news-scrape

### Developing locally

Use `docker-compose` to run things in something like the production environment. You can edit the code and see the results change when you reload the page in your browser or run the tests.

N.B. You only really need the `--build` flag below if you have changed something other than the code (e.g. dependencies) - `docker-compose` will sync any code changes to a volume inside the container.

```shell
docker-compose up --build 
...
Successfully built 24be09f203f7
Successfully tagged newsscrape_web:latest
Recreating newsscrape_web_1 ...
Recreating newsscrape_web_1 ... done
Attaching to newsscrape_web_1
web_1  |  * Running on http://0.0.0.0:5000/ (Press CTRL+C to quit)
web_1  |  * Restarting with stat
web_1  |  * Debugger is active!
web_1  |  * Debugger PIN: 294-308-829
web_1  | 192.168.99.1 - - [21/Sep/2017 00:49:56] "GET /login HTTP/1.1" 405 -
```

Use `docker-machine ip` to get the IP address to plug into your browser, or just look in the `docker-compose` logs. It was `192.168.99.1` on my machine.

### Tests

You can modify tests outside the container and run them periodically using `pytest` within the container.

I experimented with using `pytest-watch` so that tests would rerun anytime you changed something, but there was a very annoying (and undocumented) incompatibility with the `flask` autoload/debugging behavior. So don't try that and expect the web server to refresh properly without further futzing around. Bummer ...


```shell
# run a container with a mounted volume containing the code
# on your machine
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