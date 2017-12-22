# -*- coding: utf-8 -*-

from mastodon import *
import time, re, sys, os, json, random, io, gc, unicodedata
import threading, requests, pprint, codecs, MeCab, queue, urllib
from time import sleep
from datetime import datetime,timedelta
from pytz import timezone
import warnings, traceback
from xml.sax.saxutils import unescape as unesc
#from xml.dom.minidom import parseString
#from html.parser import HTMLParser
#import asyncio
from bs4 import BeautifulSoup
from os.path import join, dirname
from dotenv import load_dotenv
from gensim.models import word2vec,doc2vec
import sqlite3
import Toot_summary,GenerateText,PrepareChain  #自前のやつー！

INTERVAL = 1
COOLING_TIME = 30
DELAY = 2
STATUSES_DB_PATH = "db/statuses.db"
pat1 = re.compile(r' ([!-~ぁ-んァ-ン] )+|^([!-~ぁ-んァ-ン] )+| [!-~ぁ-んァ-ン]$')  #[!-~0-9a-zA-Zぁ-んァ-ン０-９ａ-ｚ]
pat2 = re.compile(r'[ｗ！？!\?]')
pat3 = re.compile(r'アンケート|ﾌﾞﾘﾌﾞﾘ|:.+:|.+年.+月|friends\.nico|(.)\1{5,500}|href')

tagger      = MeCab.Tagger('-Owakati -d /usr/lib/mecab/dic/mecab-ipadic-neologd -u ./dic/name.dic,./dic/id.dic,./dic/nicodic.dic')
model       = word2vec.Word2Vec.load('db/nico.model')
image_model = doc2vec.Doc2Vec.load('db/media.model')

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

MASTODON_URL = os.environ.get("MASTODON_URL")
mastodon = Mastodon(
    client_id="txt/my_clientcred_nico.txt",
    access_token="txt/my_usercred_nico.txt",
    api_base_url=MASTODON_URL)  # インスタンス
queue = queue.Queue()
hanalist = []
for i in range(1024):
    hanalist.append('花')
for i in range(16):
    hanalist.append('🌷')
    hanalist.append('🌸')
    hanalist.append('🌹')
    hanalist.append('🌺')
    hanalist.append('🌻')
    hanalist.append('🌼')
for i in range(4):
    hanalist.append('🐽')
    hanalist.append('👃')
hanalist.append('🌷🌸🌹🌺🌻🌼大当たり！🌼🌻🌺🌹🌸🌷  @kiritan')


class men_toot(StreamListener):
    def on_update(self, status):
        print("===ホームタイムライン===")
        #if  status["account"]["username"] != "kiri_bot01":
        #    queue.put(status) #トゥートをキューに入れるよー！

    def on_notification(self, notification):
        print("===通知===")
        if  notification["account"]["username"] != "kiri_bot01":
            if notification["type"] == "mention":
                status = notification["status"]
                queue.put(status)

class res_toot(StreamListener):
    def on_update(self, status):
        #print("===ローカルタイムライン===")
        if  status["account"]["username"] != "kiri_bot01":
            queue.put(status)
            quick_rtn(status)
        cm.count()

    def on_delete(self, status_id):
        print(str("===削除されました【{}】===").format(str(status_id)))
        pass  #特に処理しないよー！

def toot(toot_now, g_vis, rep=None, spo=None, media_ids=None):
    mastodon.status_post(status=toot_now, visibility=g_vis, in_reply_to_id=rep, spoiler_text=spo, media_ids=media_ids)
    print("🆕toot:" + toot_now[0:20] + ":" + g_vis )

def fav_now(fav):  # ニコります
    mastodon.status_favourite(fav)
    print("🙆Fav")

def t_local():
    try:
        listener = res_toot()
        mastodon.local_stream(listener)
    except:
        with open('error.log', 'a') as f:
            traceback.print_exc(file=f)
        print("例外情報\n" + traceback.format_exc())
        sleep(30)
        t_local()

def t_user():
    try:
        listener = men_toot()
        mastodon.user_stream(listener)
    except:
        with open('error.log', 'a') as f:
            traceback.print_exc(file=f)
        print("例外情報\n" + traceback.format_exc())
        sleep(30)
        t_user()

def quick_rtn(status):
    content = content_cleanser(status['content'])
    id = status["id"]
    username = "@" +  status["account"]["acct"]
    try:
        if re.compile("きりぼっと").search(content) or username == '@JC':
            fav_now(id)
            sleep(1)
        if re.compile(u"草").search(content):
            toot_now = ":" + username + ": " + username + " "
            if random.randint(0,7) == 3:
                random.shuffle(hanalist)
                toot_now += hanalist[0]
                toot(toot_now, "direct", id, None)
                sleep(1)
    except:
        with open('error.log', 'a') as f:
            traceback.print_exc(file=f)
        print("例外情報\n" + traceback.format_exc())


def worker():
    while True:
        sleep(INTERVAL)
        if  queue.empty():
            pass
        else:
            status = queue.get() #キューからトゥートを取り出すよー！
            content = content_cleanser(status['content'])
            acct = status["account"]["acct"]
            id = status["id"]
            if content == "緊急停止" and acct == 'kiritan':
                print("＊＊＊＊＊＊＊＊＊＊＊緊急停止したよー！＊＊＊＊＊＊＊＊＊＊＊")
                return
            elif pat3.search(content):
                pass
            else:
                print("===worker受信===")
                print(content)
                try:
                    if re.compile("(連想|れんそう)(サービス|さーびす)[：:]").search(content):
                        rensou_game(status)
                    elif re.compile("(画像検索)(サービス|さーびす)[：:]").search(content):
                        search_image(status)
                    elif re.compile("(スパウザー)(サービス|さーびす)[：:]").search(content):
                        supauza(status)
                    elif len(content) > 140:
                        gen_txt = Toot_summary.summarize(pat1.sub("",pat2.sub("",content)),limit=30,lmtpcs=1, m=1, f=4)
                        if is_japanese(gen_txt):
                            if len(gen_txt) > 5:
                                print(gen_txt + ":" + id)
                                gen_txt +=  "\n#きり要約 #きりぼっと"
                                toot(gen_txt, "public", None, "勝手に要約サービス")

                except:
                    with open('error.log', 'a') as f:
                        traceback.print_exc(file=f)
                    print("例外情報\n" + traceback.format_exc())
                    toot("@" + status["account"]["acct"] + " なんかだめだったー…ごめんねー…\n#きりぼっと", status["visibility"], status["id"], None)

                sleep(cm.get_coolingtime())

def timer_tooter():
    while True:
        sleep(10)
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        mm = jst_now.strftime("%M")
        if mm == '15' or mm == '45':
        #if mm != '99':
            spoiler = "勝手にものまねサービス"
            ymd = int((jst_now - timedelta(hours=1)).strftime("%Y%m%d"))
            hh = (jst_now - timedelta(hours=1)).strftime("%H")
            hh0000 = int(hh + "0000")
            hh9999 = int(hh + "9999")

            con = sqlite3.connect(STATUSES_DB_PATH)
            c = con.cursor()
            c.execute( r"select acct from statuses where (date = ?) and time >= ? and time <= ? and acct <> ?", [ymd,hh0000,hh9999,'kiri_bot01'] )
            toots = ""
            #print(c.fetchall())
            acct_list = []
            for row in c.fetchall():
                if row[0] not in acct_list:
                    acct_list.append(row[0])
            #print(acct_list)
            random_acct = acct_list[random.randint(0, len(acct_list)-1) ]
            con.close()
            print(random_acct)

            con = sqlite3.connect(STATUSES_DB_PATH)
            c = con.cursor()
            c.execute( r"select content from statuses where acct = ?", (random_acct,) )
            toots = ""
            for row in c.fetchall():
                content = content_cleanser(row[0])
                if pat3.search(content) or len(content) == 0:
                    pass
                else:
                    toots += content + "。\n"
            con.close()

            chain = PrepareChain.PrepareChain("user_toots",toots)
            triplet_freqs = chain.make_triplet_freqs()
            chain.save(triplet_freqs, True)

            generator = GenerateText.GenerateText(5)
            gen_txt = generator.generate("user_toots")
            gen_txt = "@" + random_acct + " :@" + random_acct + ":＜「" + gen_txt + "」"
            gen_txt = gen_txt.replace('\n',"")
            #gen_txt +=  "\n#きりものまね #きりぼっと"
            print(gen_txt)

            if len(gen_txt) > 10:
                toot(gen_txt, "direct", None, spoiler)

            sleep(60)

def summarize_tooter():
    while True:
        sleep(5)
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        mm = jst_now.strftime("%M")
        if mm == '02':
        #if mm != '99':
            ymd = int((jst_now - timedelta(hours=1)).strftime("%Y%m%d"))
            hh = (jst_now - timedelta(hours=1)).strftime("%H")
            hh0000 = int(hh + "0000")
            hh9999 = int(hh + "9999")
            spoiler = "ＬＴＬここ1時間の自動まとめ"
            con = sqlite3.connect(STATUSES_DB_PATH)
            c = con.cursor()
            c.execute( r"select content from statuses where (date = ?) and time >= ? and time <= ? and acct <> ?", (ymd,hh0000,hh9999,'kiri_bot01') )
            toots = ""
            for row in c.fetchall():
                content = content_cleanser(row[0])
                if pat3.search(content) or len(content) == 0:
                    pass
                else:
                    toots += content + "。\n"
            con.close()
            #toots = re.sub("[「」]", "", toots)
            gen_txt = Toot_summary.summarize(pat1.sub("",pat2.sub("",toots)),limit=90, lmtpcs=5, m=1, f=4)
            if len(gen_txt) > 5:
                gen_txt +=  "\n#きりまとめ #きりぼっと"
                #print(gen_txt)
                toot(gen_txt, "public", None, spoiler)
                #toot( "@kiritan \n" + gen_txt, "direct", None, spoiler)
                #sleep(10)
                sleep(60)

def rensou_game(status):
    sleep(DELAY)
    username = "@" +  status["account"]["username"]
    content = content_cleanser(status['content'])
    g_vis = status["visibility"]
    id = status["id"]
    fav_now(id)
    if len(content) > 60:
        sleep(DELAY)
        toot("長いよー！₍₍ ◝(* ,,Ծ‸Ծ,, )◟ ⁾⁾ぷーぷーダンスーー♪", g_vis ,id if g_vis != "public" else None,None)
        return

    split = re.search("(連想|れんそう)(サービス|さーびす)[：:](.*)", str(content)).group(3).split("\n",1)
    word = split[0]
    nega_w = ""
    nega_wakati = ""
    spoiler = "「" + word + "」に関連するキーワード"
    if len(split) > 1:
        nega_w = split[1]
        spoiler = spoiler + " ※ただし「" + nega_w + "」の要素を引き算"

    toot_now = ":" + username + ": "
    toot_now = username + "\n"

    wakati = " ".join(re.sub(u' [!-~ぁ-んァ-ン] ', " ", tagger.parse(word)).split() )
    print(word + "→" + wakati )

    if nega_w != "":
        nega_wakati = tagger.parse(nega_w)
        nega_wakati = re.sub(u' [!-~ぁ-んァ-ン] ', " ", nega_wakati)
        print(nega_w + "→" + nega_wakati)

    try:
        results = model.most_similar(positive=wakati.split(),negative=nega_wakati.split())
        for result in results:
            print(result[0])
            toot_now = toot_now + "{:.4f} ".format(result[1]) + result[0] + "\n"

        if toot_now != "":
            toot_now = toot_now +  "\n#連想サービス #きりぼっと"
            sleep(DELAY)
            toot(toot_now, g_vis ,id if g_vis != "public" else None,spoiler)

    except Exception as e:
        with open('error.log', 'a') as f:
            traceback.print_exc(file=f)
        pass
        print(e)
        toot_now = toot_now +  "連想できなかったー……ごめんねー……\n#連想サービス #きりぼっと"
        sleep(DELAY)
        toot(toot_now, g_vis ,id if g_vis != "public" else None,spoiler)

def search_image(status):
    sleep(DELAY)
    username = "@" +  status["account"]["username"]
    display_name = status["account"]["display_name"]
    content = content_cleanser(status['content'])
    g_vis = status["visibility"]
    id = status["id"]
    fav_now(id)
    if len(content) > 60:
        sleep(DELAY)
        toot("長いよー！₍₍ ◝(* ,,Ծ‸Ծ,, )◟ ⁾⁾ぷーぷーダンスーー♪", g_vis ,id if g_vis != "public" else None,None)
        return
    word = re.search("(画像検索)(サービス|さーびす)[：:](.*)", str(content)).group(3)
    spoiler = "「" + word + "」に関連する画像"
    toot_now = ":" + username + ": " + username + "\n"

    wakati = display_name + ' ' + re.sub(u' [!-~ぁ-んァ-ン] ', " ", tagger.parse(word))
    print(word + "→" + wakati )

    try:
        x = image_model.infer_vector(wakati.split(' '))
        results = image_model.docvecs.most_similar(positive=[x], topn=16)
    except Exception as e:
        with open('error.log', 'a') as f:
            traceback.print_exc(file=f)
        print("見つからなかったー……ごめんねー……")
        print(e)
        toot_now = toot_now +  "見つからなかったー……ごめんねー……\n#画像検索サービス #きりぼっと"
        sleep(DELAY)
        toot(toot_now, g_vis ,id if g_vis != "public" else None,spoiler)

    media_files = []
    for result in results:
        #print("画像URL:" + result[0])
        content_type = "image/" + result[0].split(".")[-1]
        if content_type == 'jpg':
            content_type = 'jpeg'
        if content_type == 'image/jpeg' or content_type == 'image/png' or content_type == 'image/gif':
            #print("content_type:" + content_type)
            try:
                dlpath = download(result[0], "media")
                #print("dlpath:" + dlpath)
                media_files.append(mastodon.media_post(dlpath, content_type))
                toot_now = toot_now + "{:.4f} ".format(result[1]) + result[0] + "\n"
                if len(media_files) >= 4:
                    break
            except Exception as e:
                with open('error.log', 'a') as f:
                    traceback.print_exc(file=f)
                print("ダウンロードできなかったー！")
                print(e)

    if toot_now != "":
        toot_now = toot_now +  "\n#画像検索サービス #きりぼっと"
        sleep(DELAY)
        try:
            toot(toot_now, g_vis ,id if g_vis != "public" else None,spoiler,media_files)
        except Exception as e:
            with open('error.log', 'a') as f:
                traceback.print_exc(file=f)
            print("投稿できなかったー！")
            print(e)

def supauza(status):
    sleep(DELAY)
    username = "@" +  status["account"]["username"]
    content = content_cleanser(status['content'])
    g_vis = status["visibility"]
    id = status["id"]
    fav_now(id)
    if len(content) > 60:
        sleep(DELAY)
        toot("長いよー！₍₍ ◝(* ,,Ծ‸Ծ,, )◟ ⁾⁾ぷーぷーダンスーー♪", g_vis ,id if g_vis != "public" else None,None)
        return
    word = re.search("(スパウザー)(サービス|さーびす)[：:](.*)", str(content)).group(3)
    word = "".join(re.sub(u' [!-~ぁ-んァ-ン] ', " ", tagger.parse(word)).split() )
    spoiler = "「" + word + "」の戦闘力を測定！ぴぴぴっ！・・・"
    toot_now = ":" + username + ": " + username + "\n"
    g_vis = status["visibility"]

    word = re.sub(u' [!-~ぁ-んァ-ン] ', " ",word )

    f = open(".dic_supauza", 'r')
    dic = json.load(f)
    f.close()

    score = {}
    for key,list in dic.items():
        score[key] = simizu(word,list)/len(list) * 1000
        print(key + ":\t\t" + str(score[key]))

    #総合戦闘力補正
    rev = score["total"] * 5
    for key,val in score.items():
        rev += val
    score["total"] += rev

    toot_now += "エロ：" +  '{0:4.0f}'.format(score["ero"]) + "k\n"
    toot_now += "汚さ：" +  '{0:4.0f}'.format(score["dirty"]) + "k\n"
    toot_now += "炒飯：" +  '{0:4.0f}'.format(score["chahan"]) + "k\n"
    toot_now += "アホ：" +  '{0:4.0f}'.format(score["aho"]) + "k\n"
    toot_now += "挨拶：" +  '{0:4.0f}'.format(score["hello"]) + "k\n"
    toot_now += "ﾆｬｰﾝ：" +  '{0:4.0f}'.format(score["nyan"]) + "k\n"
    toot_now += "総合：" +  '{0:4.0f}'.format(score["total"]) + "k\n"

    toot_now = toot_now +  "※単位：1kは昆布1枚分に相当する。\n\n"

    #図鑑風説明文
    generator = GenerateText.GenerateText()
    gen_txt = generator.generate("poke")

    toot_now = toot_now + gen_txt + "\n#スパウザーサービス #きりぼっと"
    sleep(DELAY)
    try:
        toot(toot_now, g_vis ,id if g_vis != "public" else None,spoiler)
    except Exception as e:
        with open('error.log', 'a') as f:
            traceback.print_exc(file=f)
        print("測定不能……だと……！？")
        print(e)
        toot_now = toot_now +  "測定不能……だと……！？\n#スパウザーサービス #きりぼっと"
        sleep(DELAY)
        toot(toot_now, g_vis ,id if g_vis != "public" else None,spoiler)

def simizu(word1,words2):
    sum = 0.0
    for word2 in words2:
        try:
            sum += model.similarity(word1, word2)
        except Exception as e:
            with open('error.log', 'a') as f:
                traceback.print_exc(file=f)
            print(e)
    return sum

def get_file_name(url):
    return url.split("/")[-1]

def download(url, save_path):
    req = urllib.request.Request(url)
    req.add_header("User-agent", "kiritan downloader made by @kiritan")
    source = urllib.request.urlopen(req).read()
    ret_path = save_path + "/" + get_file_name(url)
    with open(ret_path, 'wb') as file:
        file.write(source)
    return ret_path

def is_japanese(string):
    for ch in string:
        #print("ch" + ch)
        name = unicodedata.name(ch)
        if "CJK UNIFIED" in name  or "HIRAGANA" in name  or "KATAKANA" in name:
            return True
    return False

def content_cleanser(content):
    #tmp = BeautifulSoup(content.replace("<br />","\n"),'lxml').p.string
    tmp = unesc(re.sub("<span.+</span>|<a.+</a>|<p>|</p>","",re.sub("<br />", "。\n", content)))
    if tmp == None:
        return ""
    else:
        return tmp

class CoolingManager():
    def __init__(self):
        self.toot_count = 0
        self.time = 0.0
        threading.Thread(target=self.timer).start()
        threading.Thread(target=self.timer_reseter).start()
    def count(self):
        self.toot_count += 1
    def timer(self):
        while True:
            sleep(1)
            self.time += 1
    def timer_reseter(self):
        while True:
            sleep(60)
            self.time = 0.0
            self.toot_count = 0
    def get_coolingtime(self):
        if self.time == 0:
            return DELAY
        else:
            return (self.toot_count / self.time) * COOLING_TIME  + DELAY

if __name__ == '__main__':
    cm = CoolingManager()
    threading.Thread(target=t_local).start()
    threading.Thread(target=t_user).start()
    threading.Thread(target=worker).start()
    threading.Thread(target=timer_tooter).start()
    threading.Thread(target=summarize_tooter).start()
