FROM ubuntu:latest
RUN apt-get update && apt-get install -y software-properties-common
RUN apt-get install -y python3-pip python3-dev build-essential
RUN pip3 install --upgrade pip
ENV DEBIAN_FRONTEND noninteractive

ADD ./requirements.txt /tmp/requirements.txt

# Install dependencies
RUN pip install -r /tmp/requirements.txt
RUN python3 -c 'import nltk; nltk.download("punkt")'

# Add our code
ADD ./webapp /opt/webapp/
WORKDIR /opt/webapp

# To deploy locally
CMD python3 app.py
