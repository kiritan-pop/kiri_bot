FROM python:3.13-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Tokyo 

# システムパッケージのインストール
# opencv-headless にしたため、libgl1-mesa-dev 等は削除可能
# 必要最小限のビルドツールと日本語ロケールのみインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    libraqm-dev \
    fonts-takao \
    locales \
    && localedef -f UTF-8 -i ja_JP ja_JP.UTF-8 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# pipのアップグレード
RUN pip3 install --no-cache-dir --upgrade pip setuptools

# ライブラリのインストール
COPY requirements.txt .
# --no-cache-dir でイメージサイズを抑制
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードのコピーなどはこの後
# COPY . /app ...