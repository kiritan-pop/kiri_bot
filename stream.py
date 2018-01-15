# -*- coding: utf-8 -*-

from mastodon import Mastodon,StreamListener
import time, re, sys, os, json, random, io, gc, unicodedata
import threading, requests, pprint, codecs, MeCab, queue, urllib
from time import sleep
from datetime import datetime,timedelta
from pytz import timezone
import warnings, traceback
from bs4 import BeautifulSoup
from os.path import join, dirname
from dotenv import load_dotenv
from gensim.models import word2vec,doc2vec
import sqlite3
import Toot_summary,GenerateText,PrepareChain,bottlemail  #自前のやつー！
#import lstm_kiri  #どうやらimportと別のスレッドでは動作しない模様。ヒントは以下。 https://github.com/keras-team/keras/issues/2397
#graph = tf.get_default_graph()
#global graph
#with graph.as_default():
#   (... do inference here ...)

BOT_ID = 'kiri_bot01'
INTERVAL = 0.1
COOLING_TIME = 10
DELAY = 1
STATUSES_DB_PATH = "db/statuses.db"
pat1 = re.compile(r' ([!-~ぁ-んァ-ン] )+|^([!-~ぁ-んァ-ン] )+| [!-~ぁ-んァ-ン]$',flags=re.MULTILINE)  #[!-~0-9a-zA-Zぁ-んァ-ン０-９ａ-ｚ]
pat2 = re.compile(r'[ｗ！？!\?]')
#pat3 = re.compile(r'アンケート|ﾌﾞﾘﾌﾞﾘ|:.+:|.+年.+月|friends\.nico|href')
pat3 = re.compile(r'アンケート|うんこ|[ちチ][んン][こコ]|[まマ][んン][こコ]|おっぱい|[チち][んン][ポぽ]|膣|勃起|セックス|アナル|シコ[るっ]|射精')

#lk = lstm_kiri.Lstm_kiri()
tagger      = MeCab.Tagger('-Owakati -d /usr/lib/mecab/dic/mecab-ipadic-neologd -u ./dic/name.dic,./dic/id.dic,./dic/nicodic.dic')
model       = word2vec.Word2Vec.load('db/nico.model')
image_model = doc2vec.Doc2Vec.load('db/media.model')

#.envファイルからトークンとかURLを取得ー！
dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)
MASTODON_URL = os.environ.get("MASTODON_URL")
MASTODON_ACCESS_TOKEN = os.environ.get("MASTODON_ACCESS_TOKEN")

mastodon = Mastodon(
    access_token=MASTODON_ACCESS_TOKEN,
    api_base_url=MASTODON_URL)  # インスタンス

TQ = queue.Queue()
TQ2 = queue.Queue()

# 花宅配サービス用の花リスト
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

#######################################################
# クーリングタイム管理
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
            return (self.toot_count / self.time)  * COOLING_TIME  + DELAY

#######################################################
# マストドンＡＰＩ用部品を継承して、通知時の処理を実装ー！
class men_toot(StreamListener):
    def on_notification(self, notification):
        print("===通知===")
        if  notification["account"]["username"] != BOT_ID:
            if notification["type"] == "mention":
                status = notification["status"]
                TQ.put(status)

#######################################################
# マストドンＡＰＩ用部品を継承して、ローカルタイムライン受信時の処理を実装ー！
class res_toot(StreamListener):
    def on_update(self, status):
        #print("===ローカルタイムライン===")
        if  status["account"]["username"] != BOT_ID:
            TQ.put(status)
            cm.count()

    def on_delete(self, status_id):
        print(str("===削除されました【{}】===").format(str(status_id)))

#######################################################
# トゥート処理
def toot(toot_now, g_vis, rep=None, spo=None, media_ids=None):
    mastodon.status_post(status=toot_now[0:450], visibility=g_vis, in_reply_to_id=rep, spoiler_text=spo, media_ids=media_ids)
    print("🆕toot:" + toot_now[0:20] + ":" + g_vis )

#######################################################
# ファボ処理
def fav_now(fav):  # ニコります
    mastodon.status_favourite(fav)
    print("🙆Fav")

#######################################################
# ローカルタイムラインの取得設定
def th_local():
    try:
        listener = res_toot()
        mastodon.stream_local(listener)
    except:
        with open('error.log', 'a') as f:
            traceback.print_exc(file=f)
        print("例外情報\n" + traceback.format_exc())
        sleep(30)
        th_local()

#######################################################
# ユーザータイムラインの取得設定
def th_user():
    try:
        listener = men_toot()
        mastodon.stream_user(listener)
    except:
        with open('error.log', 'a') as f:
            traceback.print_exc(file=f)
        print("例外情報\n" + traceback.format_exc())
        sleep(30)
        th_user()

#######################################################
# 即時応答処理ー！
def quick_rtn(content, acct, id, g_vis):
    username = "@" +  acct
    if content == "緊急停止" and acct == 'kiritan':
        print("＊＊＊＊＊＊＊＊＊＊＊緊急停止したよー！＊＊＊＊＊＊＊＊＊＊＊")
        toot("@kiritan 緊急停止しまーす！", 'direct', id ,None)
        sys.exit()
    try:
        if re.compile(r"きりぼっと").search(content): # or username == '@JC' or username == '@kiritan':
            fav_now(id)
        if re.compile(r"草").search(content):
            toot_now = ":" + username + ": " + username + " "
            if random.randint(0,7) == 3:
                random.shuffle(hanalist)
                toot_now += hanalist[0]
                toot(toot_now, "direct", id, None)
        if re.compile(r"^:twitter:.+🔥$").search(content):
            toot_now = ":" + username + ": " + username + " "
            toot_now += '\n:twitter: ＜ﾊﾟﾀﾊﾟﾀｰ\n川\n\n🔥'
            toot(toot_now, "direct", id, None)
        if re.compile(r"ブリブリ|ぶりぶり|うん[ちこ]|💩").search(content):
            toot_now = '🌊🌊🌊 ＜ざばーっ！'
            toot(toot_now, "public", None, None)
        if re.compile(r"^ぬるぽ$").search(content):
            toot_now = 'ｷﾘｯ'
            toot(toot_now, "public", None, None)
        if re.compile(r"^33-4$").search(content):
            toot_now = 'ﾅﾝ'
            toot(toot_now, "public", None, None)
        if re.compile(r"^ちくわ大明神$").search(content):
            toot_now = 'ﾀﾞｯ'
            toot(toot_now, "public", None, None)
    except:
        with open('error.log', 'a') as f:
            traceback.print_exc(file=f)
        print("例外情報\n" + traceback.format_exc())

#######################################################
# トゥート内容の標準化・クレンジング
def content_cleanser(content):
    tmp = BeautifulSoup(content.replace("<br />","___R___").strip(),'lxml')
    hashtag = ""
    for x in tmp.find_all("a",rel="tag"):
        hashtag = x.span.text
    for x in tmp.find_all("a"):
        x.extract()

    if tmp.text == None or pat3.search(tmp.text):
        return ""
    else:
        rtext = ''
        ps = []
        for p in tmp.find_all("p"):
            ps.append(p.text)
        rtext += '。\n'.join(ps)
        rtext = unicodedata.normalize("NFKC", rtext)
        rtext = rtext.replace(r"([^:])@",r"\1")
        rtext = rtext.replace("#","")
        rtext = re.sub(r'(___R___)\1{2,}', r'\1', rtext)
        #rtext = re.sub(r'([^。|^？|^！|^\?|^!])___R___', r'\1。\n', rtext)
        rtext = re.sub(r'___R___', r'\n', rtext)
        if hashtag != "":
            return rtext + " #" + hashtag
        else:
            return rtext

#######################################################
# 連想サービス
def rensou_game(content, acct, id, g_vis):
    username = "@" +  acct
    fav_now(id)
    if len(content) == 0:
        return
    if len(content) > 60:
        toot(username + "\n₍₍ ◝(* ,,Ծ‸Ծ,, )◟ ⁾⁾長いよー！", g_vis ,id,None)
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
    if nega_w != "":
        nega_wakati = tagger.parse(nega_w)
        nega_wakati = re.sub(u' [!-~ぁ-んァ-ン] ', " ", nega_wakati)

    try:
        results = model.most_similar(positive=wakati.split(),negative=nega_wakati.split())
        for result in results:
            toot_now = toot_now + "{:.4f} ".format(result[1]) + result[0] + "\n"

        if toot_now != "":
            toot_now = toot_now +  "\n#連想サービス #きりぼっと"
            sleep(DELAY)
            #toot(toot_now, g_vis ,id if g_vis != "public" else None,spoiler)
            toot(toot_now, g_vis ,id,spoiler)

    except Exception as e:
        with open('error.log', 'a') as f:
            traceback.print_exc(file=f)
        print(e)
        toot_now = toot_now +  "連想できなかったー……ごめんねー……\n#連想サービス #きりぼっと"
        sleep(DELAY)
        toot(toot_now, g_vis ,id,spoiler)

#######################################################
# 画像検索サービス
def search_image(content, acct, id, g_vis):
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

    username = "@" +  acct
    fav_now(id)
    if len(content) == 0:
        return
    if len(content) > 60:
        sleep(DELAY)
        toot("長いよー！₍₍ ◝(* ,,Ծ‸Ծ,, )◟ ⁾⁾ぷーぷーダンスーー♪", g_vis ,id,None)
        return
    word = re.search("(画像検索)(サービス|さーびす)[：:](.*)", str(content)).group(3)
    spoiler = "「" + word + "」に関連する画像"
    toot_now = ":" + username + ": " + username + "\n"
    wakati = tagger.parse(word)
    try:
        x = image_model.infer_vector(wakati.split(' '))
        results = image_model.docvecs.most_similar(positive=[x], topn=16)
    except Exception as e:
        with open('error.log', 'a') as f:
            traceback.print_exc(file=f)
        print(e)
        toot_now = toot_now +  "見つからなかったー……ごめんねー……\n#画像検索サービス #きりぼっと"
        sleep(DELAY)
        toot(toot_now, g_vis ,id ,spoiler)
    media_files = []
    for result in results:
        content_type = "image/" + result[0].split(".")[-1]
        if content_type == 'jpg':
            content_type = 'jpeg'
        if content_type == 'image/jpeg' or content_type == 'image/png' or content_type == 'image/gif':
            try:
                dlpath = download(result[0], "media")
                media_files.append(mastodon.media_post(dlpath, content_type))
                toot_now = toot_now + "{:.4f} ".format(result[1]) + get_file_name(result[0]) + "\n"
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
            toot(toot_now, g_vis ,id,spoiler,media_files)
        except Exception as e:
            with open('error.log', 'a') as f:
                traceback.print_exc(file=f)
            print("投稿できなかったー！")
            print(e)

#######################################################
# 日本語っぽいかどうか判定
def is_japanese(string):
    for ch in string:
        name = unicodedata.name(ch,"other")
        if "CJK UNIFIED" in name  or "HIRAGANA" in name  or "KATAKANA" in name:
            return True
    return False

#######################################################
# スパウザーサービス
def supauza(content, acct, id, g_vis):
    # 類似度判定（戦闘力測定）
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
    username = "@" +  acct
    fav_now(id)
    if len(content) == 0:
        return
    if len(content) > 60:
        sleep(DELAY)
        toot(username + "\n₍₍ ◝(* ,,Ծ‸Ծ,, )◟ ⁾⁾長いよー！", g_vis ,id ,None)
        return
    word = re.search("(スパウザー)(サービス|さーびす)[：:](.*)", str(content)).group(3)
    word = tagger.parse(word)
    spoiler = "「" + word + "」の戦闘力を測定！ぴぴぴっ！・・・"
    toot_now = ":" + username + ": " + username + "\n"
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
    toot_now += "※単位：1kは昆布1枚分に相当する。\n\n"
    #図鑑風説明文
    generator = GenerateText.GenerateText()
    gen_txt = generator.generate("poke")
    toot_now = toot_now + gen_txt + "\n#スパウザーサービス #きりぼっと"
    try:
        toot(toot_now, g_vis ,id ,spoiler)
    except Exception as e:
        with open('error.log', 'a') as f:
            traceback.print_exc(file=f)
        print("測定不能……だと……！？")
        print(e)
        toot_now = toot_now +  "測定不能……だと……！？\n#スパウザーサービス #きりぼっと"
        toot(toot_now, g_vis ,id,spoiler)

#######################################################
# 料理提案サービス
def recipe_service(content, acct, id, g_vis):
    fav_now(id)
    generator = GenerateText.GenerateText(1)
    #料理名を取得ー！
    gen_txt = ''
    spoiler = "『" + generator.generate("recipe") + '』のレシピだよー！'

    #材料と分量を取得ー！
    zairyos = []
    amounts = []
    for line in open('recipe/zairyos.txt','r'):
        zairyos.append(line.strip())
    for line in open('recipe/amounts.txt','r'):
        amounts.append(line.strip())
    zairyos = random.sample(zairyos, 4)
    amounts = random.sample(amounts, 4)
    gen_txt += '＜材料＞\n'
    for z,a in zip(zairyos,amounts):
        gen_txt += ' ・' + z + '\t' + a + '\n'

    #作り方を取得ー！途中の手順と終了手順を分けて取得するよー！
    text_chu = []
    text_end = []
    while len(text_chu) <= 3 or len(text_end) < 1:
        tmp_text = generator.generate("recipe_text").strip()
        if re.search(r'完成|出来上|召し上が|できあがり',tmp_text):
            if len(text_end) <= 0:
                text_end.append(tmp_text)
        else:
            if len(text_chu) <= 3:
                text_chu.append(tmp_text)
    text_chu.extend(text_end)
    gen_txt += '＜作り方＞\n'
    for i,text in enumerate(text_chu):
        gen_txt += ' %d.'%(i+1) + text + '\n'
    gen_txt +=  "\n#きり料理提案サービス #きりぼっと"
    toot("@" + acct + "\n" + gen_txt, g_vis, id ,":@" + acct + ": " + spoiler)

#######################################################
# ボトルメールサービス　メッセージ登録
def bottlemail_service(content, acct, id, g_vis):
    fav_now(id)
    toot_now = "@" + acct + "\n"
    if len(content) == 0:
        sleep(DELAY)
        toot(toot_now + "₍₍ ◝(* ,,Ծ‸Ծ,, )◟ ⁾⁾メッセージ入れてー！", g_vis ,id,None)
        return
    if re.search(r'死|殺',content):
        sleep(DELAY)
        toot(toot_now + "₍₍ ◝(* ,,Ծ‸Ծ,, )◟ ⁾⁾ＮＧワードあるからだめー！", g_vis ,id,None)
        return
    if len(content) > 300:
        sleep(DELAY)
        toot(toot_now + "₍₍ ◝(* ,,Ծ‸Ծ,, )◟ ⁾⁾長いよー！", g_vis ,id,None)
        return

    bm = bottlemail.Bottlemail()
    word = re.search("([ぼボ][とト][るル][メめ]ー[るル])([サさ]ー[ビび][スす])[：:](.*)", str(content)).group(3)
    bm.bottling(acct,word,id)

    spoiler = "ボトルメール受け付けたよー！"
    toot_now += "受け付けたメッセージは「" + word + "」だよー！いつか届くから気長に待っててねー！"
    toot(toot_now, g_vis ,id,None)

#######################################################
# 受信したトゥートの一次振り分け処理
def th_worker():
    while True:
        sleep(INTERVAL)
        if  TQ.empty():
            pass
        else:
            print("===worker受信===")
            data = {}
            status = TQ.get() #キューからトゥートを取り出すよー！
            content = content_cleanser(status['content'])
            acct = status["account"]["acct"]
            id = status["id"]
            g_vis = status["visibility"]
            print(id,acct,content,g_vis)
            data["content"] = content
            data["acct"] = acct
            data["id"] = id
            data["g_vis"] = g_vis
            if len(content) > 0:
                # 即時処理はここで呼び出す
                quick_rtn(content=content, acct=acct, id=id, g_vis=g_vis)
                # それ以外の処理はキューに入れる
                TQ2.put(data)

#######################################################
# 受信したトゥートの二次振り分け処理（重めの処理をやるよー！）
def th_worker2():
    while True:
        sleep(INTERVAL)
        try:
            if  TQ2.empty():
                pass
            else:
                data = TQ2.get() #キューからトゥートを取り出すよー！
                content = data['content']
                id = data["id"]
                acct = data["acct"]
                g_vis = data["g_vis"]
                if re.compile("(連想|れんそう)([サさ]ー[ビび][スす])[：:]").search(content):
                    rensou_game(content=content, acct=acct, id=id, g_vis=g_vis)
                    sleep(cm.get_coolingtime())
                elif re.compile("(画像検索)([サさ]ー[ビび][スす])[：:]").search(content):
                    search_image(content=content, acct=acct, id=id, g_vis=g_vis)
                    sleep(cm.get_coolingtime())
                elif re.compile("(スパウザー)([サさ]ー[ビび][スす])[：:]").search(content):
                    supauza(content=content, acct=acct, id=id, g_vis=g_vis)
                    sleep(cm.get_coolingtime())
                elif re.compile("([ぼボ][とト][るル][メめ]ー[るル])([サさ]ー[ビび][スす])[：:]").search(content):
                    print("★ボトルメールサービス")
                    bottlemail_service(content=content, acct=acct, id=id, g_vis=g_vis)
                    sleep(cm.get_coolingtime())
                elif re.compile("(きょう|今日)の.?(料理|りょうり)|[ご御夕昼朝][食飯][食た]べ[よるた]|(腹|はら)[へ減]った|お(腹|なか)すいた|(何|なに)[食た]べよ").search(content):
                    recipe_service(content=content, acct=acct, id=id, g_vis=g_vis)
                    sleep(cm.get_coolingtime())
                elif len(content) > 140:
                    print('★要約対象：',content)
                    content = re.sub(r"(.)\1{3,}",r"\1",content, flags=(re.DOTALL))
                    gen_txt = Toot_summary.summarize(pat1.sub("",pat2.sub("",content)),limit=10,lmtpcs=1, m=1, f=4)
                    if gen_txt[-1:1] == '#':
                        gen_txt = gen_txt[:len(gen_txt)-1]
                    if is_japanese(gen_txt):
                        if len(gen_txt) > 5:
                            gen_txt +=  "\n#きり要約 #きりぼっと"
                            toot("@" + acct + " :@" + acct + ":\n"  + gen_txt, "public", id, "勝手に要約サービス")
                            sleep(cm.get_coolingtime())
        except:
            with open('error.log', 'a') as f:
                traceback.print_exc(file=f)
            print("例外情報\n" + traceback.format_exc())
            sleep(cm.get_coolingtime())

#######################################################
# 定期ものまねさーびす！
def th_timer_tooter():
    while True:
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        mm = jst_now.strftime("%M")
        if mm == '15' or mm == '45':
        #if mm != '99':
            spoiler = "勝手にものまねサービス"
            ymd = int((jst_now - timedelta(hours=1)).strftime("%Y%m%d"))
            hh = (jst_now - timedelta(hours=1)).strftime("%H")
            hh0000 = int(hh + "0000")
            hh9999 = int(hh + "9999")
            try:
                con = sqlite3.connect(STATUSES_DB_PATH)
                c = con.cursor()
                c.execute( r"select acct from statuses where (date = ?) and time >= ? and time <= ? and acct <> ?", [ymd,hh0000,hh9999,BOT_ID] )
                toots = ""
                acct_list = set([])
                for row in c.fetchall():
                    if row[0] not in acct_list:
                        acct_list.add(row[0])
                random_acct = random.sample(acct_list,1)[0]
                con.close()
                con = sqlite3.connect(STATUSES_DB_PATH)
                c = con.cursor()
                c.execute( r"select content from statuses where acct = ?", (random_acct,) )
                toots = ""
                for row in c.fetchall():
                    content = content_cleanser(row[0])
                    if len(content) == 0:
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
                gen_txt +=  "\n#きりものまね #きりぼっと"
                if len(gen_txt) > 10:
                    toot(gen_txt, "public", None, spoiler)
                sleep(60)
            except:
                with open('error.log', 'a') as f:
                    traceback.print_exc(file=f)
                print("例外情報\n" + traceback.format_exc())
                sleep(60)

#######################################################
# 定期ここ1時間のまとめ
def th_summarize_tooter():
    while True:
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
            c.execute( r"select content from statuses where (date = ?) and time >= ? and time <= ? and acct <> ?", (ymd,hh0000,hh9999,BOT_ID) )
            toots = ""
            for row in c.fetchall():
                content = content_cleanser(row[0])
                if len(content) == 0:
                    pass
                else:
                    content = re.sub(r"(.+)\1{3,}","",content, flags=(re.DOTALL))
                    toots += content + "\n"
            con.close()
            gen_txt = Toot_summary.summarize(pat1.sub("",pat2.sub("",toots)),limit=90, lmtpcs=5, m=1, f=4)
            if gen_txt[-1:1] == '#':
                gen_txt = gen_txt[:len(gen_txt)-1]
            if len(gen_txt) > 5:
                gen_txt +=  "\n#きりまとめ #きりぼっと"
                toot(gen_txt, "public", None, spoiler)
                sleep(60)

#######################################################
# ボトルメールサービス　配信処理
def th_bottlemail_sending():
    bm = bottlemail.Bottlemail()
    while True:
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        mm = jst_now.strftime("%M")
        if mm == '10':
        #if mm != '99': #test
            ymd = int((jst_now - timedelta(hours=1)).strftime("%Y%m%d"))
            hh = (jst_now - timedelta(hours=1)).strftime("%H")
            hh0000 = int(hh + "0000")
            hh9999 = int(hh + "9999")
            try:
                sendlist = bm.drifting()
                for id,acct,msg,reply_id in sendlist:
                    sleep(INTERVAL*5)
                    spoiler = ":@" + acct + ": から🍾ボトルメール💌届いたよー！"
                    con = sqlite3.connect(STATUSES_DB_PATH)
                    c = con.cursor()
                    c.execute( r"select acct from statuses where (date = ?) and time >= ? and time <= ? and acct <> ?", [ymd,hh0000,hh9999,BOT_ID] )
                    acct_list = set([])
                    for row in c.fetchall():
                        if row[0] not in acct_list:
                            acct_list.add(row[0])
                    con.close()
                    random_acct = random.sample(acct_list,1)[0]
                    print(random_acct)
                    #お届け！
                    toots = "@" + random_acct + " :@" + acct + ":＜「" + msg + "」"
                    toots +=  "\n※ボトルメールサービス：＜メッセージ＞　であなたも送れるよー！試してみてね！"
                    toots +=  "\n#ボトルメールサービス #きりぼっと"
                    toot(toots, "direct",reply_id if reply_id != 0 else None, spoiler)
                    bm.sended(id, random_acct)

                    #到着通知
                    sleep(DELAY)
                    spoiler = ":@" + random_acct + ": が🍾ボトルメール💌受け取ったよー！"
                    toots = "@" + acct + " 届けたメッセージは……\n:@" + acct + ": ＜「" + msg + "」"
                    toots +=  "\n#ボトルメールサービス #きりぼっと"
                    toot(toots, "direct", None, spoiler)

                sleep(60)
            except:
                with open('error.log', 'a') as f:
                    traceback.print_exc(file=f)
                print("例外情報\n" + traceback.format_exc())

#######################################################
# きりぼっとのつぶやき
def th_timer_tooter2():
    def lstmgentxt(seedtxt):
        import lstm_kiri
        lk = lstm_kiri.Lstm_kiri()
        rtntext = lk.gentxt(seedtxt)
        del lk,lstm_kiri
        gc.collect()
        if rtntext[0:1] == '。':
            return rtntext[1:]
        else:
            return rtntext
    while True:
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        mm = jst_now.strftime("%M")
        if mm == '57' or mm == '37': # or mm == '17':
        #if mm != '99': #test
            try:
                con = sqlite3.connect(STATUSES_DB_PATH)
                c = con.cursor()
                ymd = int(jst_now.strftime("%Y%m%d"))
                hh = jst_now.strftime("%H")
                hh0000 = int(hh + "0000")
                hh9999 = int(hh + "9999")
                c.execute( r"select content,id,acct from statuses where (date = ?) and time >= ? and time <= ? and acct <> ? order by time desc", [ymd,hh0000,hh9999, BOT_ID] )
                seeds = []
                seedtxt = ''
                id = 0
                acct = ''
                for row in c.fetchall():
                    content = content_cleanser(row[0])
                    id = row[1]
                    acct = row[2]
                    if len(content) == 0:
                        pass
                    else:
                        seeds.append(content)
                        #seedtxt = content
                        #if len(seedtxt)>30:
                        if len(seeds)>5:
                            break
                con.close()
                seeds.reverse()
                seedtxt = "".join(seeds)
                if seedtxt[-1:1] != '。':
                    seedtxt += '。'
                print('seedtxt:',seedtxt)
                gen_txt = lstmgentxt(seedtxt)
                #gen_txt = '@' + acct + ' :@' + acct + ':\n' + gen_txt
                gen_txt +=  "\n#きりつぶやき #きりぼっと"
                #toot(gen_txt, "public", id if id > 0 else None, 'きりぼっとによる補足')
                toot(gen_txt, "public", None, None)
                sleep(60)
            except:
                with open('error.log', 'a') as f:
                    traceback.print_exc(file=f)
                print("例外情報\n" + traceback.format_exc())
                sleep(60)

#######################################################
# トレーニング処理　（今は使ってないよー）
def th_lstm_trainer():
    def lstmtrain(text):
        import lstm_kiri
        lk = lstm_kiri.Lstm_kiri()
        lk.train(text)
        del lk,lstm_kiri
        gc.collect()
    while True:
        sleep(10)
        #print('th_lstm_trainer')
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        mm = jst_now.strftime("%M")
        if mm == '07':
        #if mm != '99': #test
            try:
                ymd = int((jst_now - timedelta(hours=1)).strftime("%Y%m%d"))
                hh = (jst_now - timedelta(hours=1)).strftime("%H")
                hh0000 = int(hh + "0000")
                hh9999 = int(hh + "9999")
                con = sqlite3.connect(STATUSES_DB_PATH)
                c = con.cursor()
                c.execute( r"select content from statuses where (date = ?) and time >= ? and time <= ? and acct <> ? order by time asc", [ymd,hh0000,hh9999, BOT_ID] )
                toots = []
                for row in c.fetchall():
                    content = content_cleanser(row[0])
                    if len(content) == 0:
                        pass
                    else:
                        toots.append(content)

                lstmtrain("\n".join(toots))
                con.close()
                sleep(60)
            except:
                with open('error.log', 'a') as f:
                    traceback.print_exc(file=f)
                print("例外情報\n" + traceback.format_exc())
                sleep(60)


if __name__ == '__main__':
    cm = CoolingManager()
    threading.Thread(target=th_local).start()
    threading.Thread(target=th_user).start()
    threading.Thread(target=th_worker).start()
    threading.Thread(target=th_worker2).start()
    threading.Thread(target=th_timer_tooter).start()
    threading.Thread(target=th_summarize_tooter).start()
    threading.Thread(target=th_timer_tooter2).start()
    threading.Thread(target=th_lstm_trainer).start()
    threading.Thread(target=th_bottlemail_sending).start()
