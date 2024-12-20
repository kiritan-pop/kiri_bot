# coding: utf-8

import os,re
import requests
import urllib3
import unicodedata
from bs4 import BeautifulSoup
import jaconv
from logging import getLogger, StreamHandler, Formatter, FileHandler, getLevelName, basicConfig, NOTSET
from queue import Queue, Empty

# きりぼコンフィグ
from kiribo.config import settings

from kiribo import deep


log_level = getLevelName(settings.log_level)
sh = StreamHandler()
sh.setLevel(log_level)
formatter = Formatter('%(levelname)s:%(asctime)s - %(message)s')
sh.setFormatter(formatter)

fh = FileHandler(settings.log_path)  # fh = file handler
fh.setLevel(log_level)
fh_formatter = Formatter(
    '%(levelname)s:%(asctime)s - %(filename)s - %(name)s - %(lineno)d - %(message)s')
fh.setFormatter(fh_formatter)
basicConfig(level=NOTSET, handlers=[sh, fh])

logger = getLogger(__name__)

#######################################################
# ネイティオ語翻訳
def two2jp(twotwo_text):
    twotwodic = {}
    twotwo_text = unicodedata.normalize("NFKC", twotwo_text)
    for line in open(settings.twotwo_dic_path):
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
    tmp = BeautifulSoup(content.replace("<br>","___R___").strip(),'lxml')
    hashtag = []
    for x in tmp.find_all("a",rel="tag"):
        hashtag.append(x.span.text)
    return hashtag
    # return ','.join(hashtag)

#######################################################
# トゥート内容の標準化・クレンジング
def content_cleanser(content):
    hashtag = ""
    rtext = ""

    tmp = BeautifulSoup(content.replace("<br />", "___R___").strip(), 'lxml')
    for x in tmp.find_all("a", rel="tag"):
        hashtag = x.span.text.strip()
    for x in tmp.find_all("a"):
        x.extract()
    if tmp.text == None:
        return ""

    ps = []
    for p in tmp.find_all("p"):
        ps.append(p.text)
        p.extract()
    ps.append(tmp.text)
    rtext += '\n'.join(ps).strip()
    rtext = unicodedata.normalize("NFKC", rtext)
    rtext = rtext.replace("#", "")
    rtext = re.sub(r'(___R___)\1{2,}', r'\1', rtext)
    rtext = re.sub(r'___R___', r'\n', rtext)
    rtext = rtext.strip()
    if hashtag != "":
        return rtext + " #" + hashtag
    else:
        return rtext


def replace_ng_word(text):
    # NGワード
    ng_words = read_ng_words()
    target_words = []
    nodes = deep.tagger2.parseToNodeList(normalize_txt(text))
    for node in nodes:
        if node.feature.pos1 not in ["助詞", "助動詞"]:
            target_words.append(node.surface)

    for ng_word in ng_words:
        if any([re.search(f"^{ng_word}$", target) for target in target_words]) and re.search(ng_word, text):
            logger.info(f"{ng_word=}")
            text = re.sub(
                ng_word, '■'*len(re.search(ng_word, text).group(0)), text)

    return text


def read_ng_words():
    return set(word.strip() for word in open(settings.ng_words_path).readlines())


def is_ng(text):
    #NGワード
    for ng_word in read_ng_words():
        if re.search(ng_word, text):
            return True
    return False


def normalize_txt(text):
    return jaconv.h2z(jaconv.z2h(text.strip(), kana=False, digit=True,
                                  ascii=True), kana=True, digit=False, ascii=False).lower()


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
    return rtext


def display_name_cleanser(display_name):
    return re.sub(r'(?<!:)@', '＠', display_name)


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


def download_media(url, save_path=settings.media_path, subdir=""):
    os.makedirs(os.path.join(save_path, subdir), exist_ok=True)
    filename = get_file_name(url)
    if filename:
        ret_path = os.path.join(save_path, subdir, filename)
        logger.debug("download_media start")
        try:
            response = requests.get(url, timeout=3)
        except urllib3.exceptions.ReadTimeoutError as e:
            logger.warn("requests retry")
            logger.warn(e)
            try:
                response = requests.get(url, timeout=3)
            except urllib3.exceptions.ReadTimeoutError as e1:
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


class ClearableQueue(Queue):

    def clear(self):
        try:
            while True:
                self.get_nowait()
        except Empty:
            pass


if __name__ == '__main__':
    print(replace_ng_word("テスト"))
