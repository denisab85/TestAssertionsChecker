FROM ubuntu:latest

ENV USER root
ENV DEBIAN_FRONTEND noninteractive

ARG API_VERSION='5.3.0.35.gdfbb28b'
ARG API_DOWNLOAD_URL=http://build.swifttest.com:8080/job/API_MAIN_Combo/330/artifact/dist/$API_VERSION/*zip*/$API_VERSION.zip
ARG APP_HOME=/usr/src/tac
ARG PACKAGES='python python-dev mono-complete unzip curl'

WORKDIR $APP_HOME

# isntall python and mono
RUN apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 3FA7E0328081BFF6A14DA29AA6A19B38D3D831EF && \
  echo "deb http://download.mono-project.com/repo/debian wheezy main" > /etc/apt/sources.list.d/mono-xamarin.list && \
  apt-get update && \
  apt-get install -y $PACKAGES && \
                                  \
# install API
  cd /tmp && \
  curl $API_DOWNLOAD_URL > api.zip && \
  unzip api.zip && \
  cd $API_VERSION && \
  yes | ./install_api -y && \
  rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY . $APP_HOME

COPY default.assertions /$USER/.tac/default.assertions

VOLUME /opt/swifttest/resources/dotnet/Ports
