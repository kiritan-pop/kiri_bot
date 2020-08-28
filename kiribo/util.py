# coding: utf-8

import random,json
import os,sys,io,re
import requests
import http.client
import urllib.parse
from urllib.parse import quote
from time import time, sleep
import unicodedata
import threading
from pytz import timezone
from datetime import datetime
from bs4 import BeautifulSoup
import traceback
from logging import getLogger, StreamHandler, Formatter, FileHandler, getLevelName

# きりぼコンフィグ
from kiribo.config import TWOTWO_DIC_PATH, NG_WORDS_PATH, LOG_LEVEL, LOG_PATH, MEDIA_PATH


#######################################################
# エラー時のログ書き込み
def setup_logger(modname):
    log_level = getLevelName(LOG_LEVEL)
    logger = getLogger(modname)
    logger.setLevel(log_level)

    sh = StreamHandler()
    sh.setLevel(log_level)
    formatter = Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    fh = FileHandler(LOG_PATH) #fh = file handler
    fh.setLevel(log_level)
    fh_formatter = Formatter('%(asctime)s - %(filename)s - %(name)s - %(lineno)d - %(levelname)s - %(message)s')
    fh.setFormatter(fh_formatter)
    logger.addHandler(fh)
    return logger


#######################################################
# ネイティオ語翻訳
def two2jp(twotwo_text):
    twotwodic = {}
    twotwo_text = unicodedata.normalize("NFKC", twotwo_text)
    for line in open(TWOTWO_DIC_PATH):
        tmp = line.strip().split(',')
        twotwodic[tmp[1]] = tmp[0]
    text = ""
    for two in twotwo_text.split(' '):
        if two in twotwodic:
            text += twotwodic[two]
        else:
            text += two
    return text
    # return unicodedata.normalize("NFKC", text)

#######################################################
# ハッシュタグ抽出
def hashtag(content):
    tmp = BeautifulSoup(content.replace("<br />","___R___").strip(),'lxml')
    hashtag = []
    for x in tmp.find_all("a",rel="tag"):
        hashtag.append(x.span.text)
    return hashtag
    # return ','.join(hashtag)

#######################################################
# トゥート内容の標準化・クレンジング
def content_cleanser(content):
    tmp = BeautifulSoup(content.replace("<br />","___R___").strip(),'lxml')
    hashtag = ""
    for x in tmp.find_all("a",rel="tag"):
        hashtag = x.span.text
    for x in tmp.find_all("a"):
        x.extract()

    if tmp.text == None:
        return ""

    rtext = ''
    ps = []
    for p in tmp.find_all("p"):
        ps.append(p.text)
    rtext += '。\n'.join(ps)
    rtext = unicodedata.normalize("NFKC", rtext)
    # rtext = re.sub(r'([^:])@', r'\1', rtext)
    rtext = rtext.replace("#","")
    rtext = re.sub(r'(___R___)\1{2,}', r'\1', rtext)
    rtext = re.sub(r'___R___', r'\n', rtext)
    #NGワード
    ng_words = set(word.strip() for word in open(NG_WORDS_PATH).readlines())
    for ng_word in ng_words:
        # rtext = rtext.replace(ng_word,'■■■')
        rtext = re.sub(ng_word, '■'*len(ng_word), rtext)
    if hashtag != "":
        return rtext + " #" + hashtag
    else:
        return rtext

#######################################################
# トゥート内容の標準化・クレンジング・ライト
def content_cleanser_light(text):
    rtext = re.sub(r'([^:])@', r'\1', text)
    rtext = re.sub(r'(___R___)\1{2,}', r'\1', rtext)
    rtext = re.sub(r'___R___', r'\n', rtext)
    #NGワード
    ng_words = set(word.strip() for word in open(NG_WORDS_PATH).readlines())
    for ng_word in ng_words:
        rtext = re.sub(ng_word, '■'*len(ng_word), rtext)
    return rtext

#######################################################
# メディアダウンロード
def get_file_name(url):
    filename, file_extension, *_ = url.split("/")[-1].split("?")[0].split(".")
    return filename + "." + file_extension.lower()


def download_media(url, save_path=MEDIA_PATH, subdir=""):
    os.makedirs(os.path.join(save_path, subdir), exist_ok=True)
    ret_path = os.path.join(save_path, subdir, get_file_name(url))
    with open(ret_path, 'wb') as file:
        file.write(requests.get(url, allow_redirects=True).content)
    return ret_path
