FROM ubuntu:18.04
RUN apt-get update && apt-get install -y software-properties-common
RUN apt-get install -y python3-pip python3-dev build-essential
RUN pip3 install --upgrade pip
ENV DEBIAN_FRONTEND noninteractive

# Install OpenJDK-8 - Java is required for boilerpipe 
RUN apt-get install -y openjdk-8-jdk && \
    apt-get install -y ant && \
    apt-get clean;
RUN apt-get update && \
    apt-get install ca-certificates-java && \
    apt-get clean && \
    update-ca-certificates -f;
ENV JAVA_HOME /usr/lib/jvm/java-8-openjdk-amd64/
RUN export JAVA_HOME

ADD ./requirements.txt /tmp/requirements.txt

# Install dependencies
RUN pip install -r /tmp/requirements.txt
RUN python3 -m nltk.downloader -d /usr/share/nltk_data punkt

# Our code
ADD ./webapp /opt/webapp/
WORKDIR /opt/webapp
