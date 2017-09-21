FROM ubuntu:latest
RUN apt-get update -y
RUN apt-get install -y python-pip python-dev build-essential

ADD ./requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

ADD . /code
WORKDIR /code

# Run the app.  CMD is required to run on Heroku.  $PORT is set by Heroku.
#CMD gunicorn --bind 0.0.0.0:$PORT Scrape/scrape/wsgi --timeout 6000

# Use this line for local development, rather than the gunicorn in the previous line
# $ docker-compose up --build
CMD python Scrape/scrape/app.py

