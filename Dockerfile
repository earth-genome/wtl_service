FROM ubuntu:latest
RUN apt-get update && apt-get install -y software-properties-common
RUN apt-get install -y python3-pip python3-dev build-essential
RUN pip3 install --upgrade pip
ENV DEBIAN_FRONTEND noninteractive

ADD ./requirements.txt /tmp/requirements.txt

# Install dependencies
RUN pip install -r /tmp/requirements.txt
RUN python3 -m nltk.downloader -d /usr/share/nltk_data punkt

# Our code
ADD ./webapp /opt/webapp/
ADD ./saved_models:/opt/saved_models
ADD ./bin /bin
WORKDIR /opt/webapp
