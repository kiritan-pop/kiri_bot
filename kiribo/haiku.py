# coding: utf-8

import MeCab
import random,json
import sys,io,re,gc,os
from pprint import pprint as pp
from kiribo.config import IPADIC_PATH, KIGO_PATH
from kiribo import imaging, util
logger = util.setup_logger(__name__)

tagger = MeCab.Tagger(f"-d {IPADIC_PATH}")

def haiku_check(content):
    # 形態素解析
    keitai = []
    for w in tagger.parse(content).split("\n"):
        if w == 'EOS':
            break
        temp = {}
        logger.debug(w)
        temp["origin"], w2, *_ = w.split("\t")
        if len(w2.split(",")) < 8:
            continue
        temp["hinshi1"], temp["hinshi2"], _, _, _, temp["katsuyou"], _, temp["yomi"], \
            *_ = w2.split(",")
        # 記号はスキップ
        if temp["hinshi1"] == "記号":
            continue
        # ャュョァィゥェォはカウントしない
        temp["yomi"] = re.sub(r"[ャュョァィゥェォ]", "", temp["yomi"])
        temp["len"] = len(temp["yomi"])
        keitai.append(temp)

    logger.debug(keitai)
    # ５７５判定
    haiku = []
    numlist = [5, 7, 5]
    HAIKU_LEN = len(numlist)
    ku_len = 0
    word = ""
    try:
        n = numlist.pop(0)
        k = keitai.pop(0)
        while True:
            # 句の頭に助詞が来るパターンは除外
            if ku_len == 0 and k["hinshi1"] == "助詞":
                haiku = []
                break

            ku_len += k['len']
            # オーバーしたら終了
            if ku_len > n:
                haiku = []
                break
            elif ku_len == n:
                # 動詞で未然形は除外
                if k["hinshi1"] == "動詞" and k["katsuyou"] == "未然形":
                    haiku = []
                    break
                haiku.append(word + k["origin"])
                ku_len = 0
                word = ""
                n = numlist.pop(0)
                k = keitai.pop(0)
            else:
                word += k["origin"]
                k = keitai.pop(0)
    except IndexError:
        # ピッタシ終わりじゃないと除外
        if len(keitai) > 0:
            haiku = []

    logger.debug(haiku)
    # 季語有無判定
    haiku_hantei = False
    kigo = None
    for ku in haiku:
        for k in open(KIGO_PATH).readlines():
            if k.strip() in ku:
                haiku_hantei = True
                kigo = k.strip()
                break

    return haiku, haiku_hantei, kigo

if __name__ == '__main__':
    # そうなのかなかなか判定難しそう いや別に俳句得意じゃないけどな
    # さっきから下品な川柳いやになる
    print(haiku_check(input(">>").strip()))
