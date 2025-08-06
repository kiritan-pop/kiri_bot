FROM python:3.11

ENV DEBIAN_FRONTEND noninteractive
ENV TZ=Asia/Tokyo 

RUN apt update
RUN apt install -y build-essential libssl-dev \
    libffi-dev libraqm-dev \
    libgl1-mesa-dev \
    fonts-takao

RUN apt -y install locales && \
    localedef -f UTF-8 -i ja_JP ja_JP.UTF-8
RUN pip3 install --upgrade pip
RUN pip install --upgrade setuptools

COPY requirements.txt .
RUN pip install -r requirements.txt
