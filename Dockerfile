FROM ubuntu:latest
RUN apt-get update -y
RUN apt-get install -y python-pip python-dev build-essential
ADD ./webapp/requirements.txt /tmp/requirements.txt

# Install dependencies
RUN pip install -qr /tmp/requirements.txt

# Add our code
ADD ./webapp /opt/webapp/
WORKDIR /opt/webapp	

# Run the app.  CMD is required to run on Heroku.  $PORT is set by Heroku.
# CMD gunicorn --bind 0.0.0.0:$PORT wsgi --timeout 6000

# Use this line for local development, rather than the gunicorn in the previous line
CMD python app.py

