# coding: utf-8

import random,json
import os,sys,io,re
import requests
from requests.exceptions import Timeout
import http.client
import urllib.parse
from urllib.parse import quote
from time import time, sleep
import unicodedata
import threading
from pytz import timezone
from datetime import datetime
from bs4 import BeautifulSoup
import jaconv
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


logger = setup_logger(__name__)

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
    rtext = rtext.replace("#", "")
    rtext = re.sub(r'(___R___)\1{2,}', r'\1', rtext)
    rtext = re.sub(r'___R___', r'\n', rtext)
    rtext = jaconv.h2z(jaconv.z2h(rtext, kana=False, digit=True,
                                  ascii=True), kana=True, digit=False, ascii=False)
    # rtext = re.sub(r'([^:])@', r'\1', rtext)
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
# トゥート内容の標準化・クレンジング
def reply_to(content):
    tmp = BeautifulSoup(content, 'lxml')
    reply_to_list = []
    for x in tmp.find_all("a", class_="u-url mention"):
        if x.span != None:
            reply_to_list.append(x.span.text)
    return reply_to_list

    
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

def display_name_cleanser(display_name):
    return re.sub(r'@', '＠', display_name)

#######################################################
# 日本語っぽいかどうか判定
def is_japanese(string):
    for ch in string:
        name = unicodedata.name(ch, "other")
        if "CJK UNIFIED" in name or "HIRAGANA" in name or "KATAKANA" in name:
            return True
    return False


#######################################################
# メディアダウンロード
def get_file_name(url):
    logger.debug(f'url:{url}')
    temp = url.split("/")[-1].split("?", 1)[0].split(",", 1)[0]
    filename = temp.split(".")[0]
    file_extension = temp.split(".")[-1]
    if file_extension.lower() in ["jpg", "jpeg", "png", "gif", "mp4"]:
        return filename + "." + file_extension.lower()
    return None


def download_media(url, save_path=MEDIA_PATH, subdir=""):
    os.makedirs(os.path.join(save_path, subdir), exist_ok=True)
    filename = get_file_name(url)
    if filename:
        ret_path = os.path.join(save_path, subdir, filename)
        logger.debug("download_media start")
        try:
            response = requests.get(url, timeout=2)
        except Timeout as e:
            logger.warn(e)
            logger.warn("requests retry")
            try:
                response = requests.get(url, timeout=3)
            except Timeout as e1:
                logger.warn(e1)
                return None
        
        logger.debug(f"download_media end code:{response.status_code}")
        if response.status_code == 200:
            with open(ret_path, 'wb') as file:
                file.write(response.content)
            return ret_path
        else:
            return None
    else:
        return None
