FROM ubuntu:20.04
USER root

ENV DEBIAN_FRONTEND noninteractive
ENV LANG ja_JP.UTF-8
ENV LANGUAGE ja_JP:ja
ENV LC_ALL ja_JP.UTF-8
ENV TZ JST-9
ENV TERM xterm
ENV MECABRC /etc/mecabrc

RUN apt update
RUN apt install -y python3-pip build-essential libssl-dev \
    libffi-dev python3-dev libraqm-dev mecab libmecab-dev \
    mecab-ipadic-utf8 python3-mecab \
    vim less libhdf5-dev \
    zlib1g-dev \
    libjpeg-dev \
    libwebp-dev \
    libpng-dev \
    libtiff5-dev \
    libopenexr-dev \
    libgdal-dev \
    libgtk2.0-dev \
    libdc1394-22-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libtheora-dev \
    libvorbis-dev \
    libxvidcore-dev \
    libx264-dev \
    yasm \
    libopencore-amrnb-dev \
    libopencore-amrwb-dev \
    libv4l-dev \
    libxine2-dev \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    libopencv-highgui-dev \
    libnvidia-encode-465 \
    ffmpeg \
    fonts-takao

RUN apt -y install locales && \
    localedef -f UTF-8 -i ja_JP ja_JP.UTF-8
RUN pip3 install --upgrade pip
RUN pip install --upgrade setuptools

COPY requirements.txt .
RUN pip install -r requirements.txt