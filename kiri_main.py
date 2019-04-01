# -*- coding: utf-8 -*-

from mastodon import Mastodon, StreamListener
from pprint import pprint as pp
import requests
import re, os, json, random, unicodedata, signal, sys
import threading, queue, urllib
from time import sleep
from pytz import timezone
import dateutil
from datetime import datetime,timedelta
import warnings, traceback
from os.path import join, dirname
from collections import defaultdict, Counter
from dotenv import load_dotenv
import wikipedia
import GenerateText, bottlemail, Toot_summary
import kiri_util, kiri_game, kiri_romasaga, kiri_deep
from PIL import Image, ImageOps, ImageFile, ImageChops, ImageFilter, ImageEnhance
import argparse
ImageFile.LOAD_TRUNCATED_IMAGES = True

MASTER_ID = 'kiritan'
BOT_ID = 'kiri_bot01'
DELAY = 2
pat1 = re.compile(r' ([!-~ぁ-んァ-ン] )+|^([!-~ぁ-んァ-ン] )+| [!-~ぁ-んァ-ン]$',flags=re.MULTILINE)  #[!-~0-9a-zA-Zぁ-んァ-ン０-９ａ-ｚ]
pat2 = re.compile(r'[ｗ！？!\?]')
abc = list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!?.()+-=,")

#.envファイルからトークンとかURLを取得ー！
dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)
MASTODON_URL = os.environ.get("MASTODON_URL")
MASTODON_ACCESS_TOKEN = os.environ.get("MASTODON_ACCESS_TOKEN")
# BING_KEY = os.environ.get("BING_KEY")
GOOGLE_KEY = os.environ.get("GOOGLE_KEY")
GOOGLE_ENGINE_KEY = os.environ.get("GOOGLE_ENGINE_KEY")

#得点管理、流速監視
SM = kiri_util.ScoreManager()
CM = kiri_util.CoolingManager(3)
DAO = kiri_util.DAO_statuses()
TRANS = kiri_util.trans(GOOGLE_KEY)
# painter = kiri_coloring.Painter(gpu=-1)
#しりとり用
StMG = kiri_game.Siritori_manager()


publicdon = Mastodon(api_base_url=MASTODON_URL)  # インスタンス

mastodon = Mastodon(
    access_token=MASTODON_ACCESS_TOKEN,
    api_base_url=MASTODON_URL)  # インスタンス

PostQ = queue.Queue()
WorkerQ = queue.Queue()
TimerDelQ = queue.Queue()
StatusQ = queue.Queue()
Toot1bQ = queue.Queue()
DelQ = queue.Queue()
GetNumQ = queue.Queue()
GetNumVoteQ = queue.Queue()
GetNum_flg = []
HintPintoQ = queue.Queue()
HintPinto_ansQ = queue.Queue()
HintPinto_flg = []

slot_bal = []
rep_cnt = []
rentou = []
acct_least_created_at = {}
pita_list = []

toots_for_rep = defaultdict(list)


# 花宅配サービス用の花リスト
hanalist = []
for i in range(2048):
    hanalist.append('花')
for i in range(32):
    hanalist.append('🌷')
    hanalist.append('🌸')
    hanalist.append('🌹')
    hanalist.append('🌺')
    hanalist.append('🌻')
    hanalist.append('🌼')
for i in range(16):
    hanalist.append('🐽')
    hanalist.append('👃')
hanalist.append('🌷🌸🌹🌺🌻🌼大当たり！🌼🌻🌺🌹🌸🌷  @%s'%MASTER_ID)

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gtime", type=int, default=30)
    parser.add_argument("--htime", type=int, default=20)
    args = parser.parse_args()
    return args

#######################################################
# マストドンＡＰＩ用部品を継承して、通知時の処理を実装ー！
class notification_listener(StreamListener):
    def on_notification(self, notification):
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        ymdhms = jst_now.strftime("%Y%m%d %H%M%S")
        # print("%s===notification_listener on_notification==="%ymdhms)

        if notification["type"] == "mention":
            status = notification["status"]
            CM.count(status['created_at'])
            WorkerQ.put(status)
            vote_check(status)
            # SM.update(notification["status"]["account"]["acct"], 'reply')
        elif notification["type"] == "favourite":
            SM.update(notification["account"]["acct"], 'fav', ymdhms)
        elif notification["type"] == "reblog":
            SM.update(notification["account"]["acct"], 'boost', ymdhms)
        elif notification["type"] == "follow":
            SM.update(notification["account"]["acct"], 'boost', ymdhms)
            follow(notification["account"]["id"])
    def on_update(self, status):
        HintPinto_ans_check(status)
        # 時限トゥート用（自分のトゥートのみ）
        acct = status["account"]["acct"]
        if acct == BOT_ID:
            TimerDelQ.put(status)

#######################################################
# マストドンＡＰＩ用部品を継承して、ローカルタイムライン受信時の処理を実装ー！
class ltl_listener(StreamListener):
    def on_update(self, status):
        # jst_now = datetime.now(timezone('Asia/Tokyo'))
        # ymdhms = jst_now.strftime("%Y%m%d %H%M%S")
        # print("%s===ltl_listener on_update==="%ymdhms)
        #mentionはnotificationで受けるのでLTLのはスルー！(｢・ω・)｢ 二重レス防止！
        if re.search(r'[^:]@' + BOT_ID, status['content']):
            return
        acct = status["account"]["acct"]
        if acct != BOT_ID:
            WorkerQ.put(status)

#######################################################
# タイムライン保存用（認証なし）
class public_listener(StreamListener):
    def on_update(self, status):
        # jst_now = datetime.now(timezone('Asia/Tokyo'))
        # ymdhms = jst_now.strftime("%Y%m%d %H%M%S")
        # print("%s===public_listener on_update==="%ymdhms)
        StatusQ.put(status)
        CM.count(status['created_at'])

    def on_delete(self, status_id):
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        ymdhms = jst_now.strftime("%Y%m%d %H%M%S")
        print("{0}===public_listener on_delete【{1}】===".format(ymdhms,str(status_id)))
        DelQ.put(status_id)

#######################################################
# トゥート処理
def toot(toot_now, g_vis='direct', rep=None, spo=None, media_ids=None, interval=0):
    def qput(toot_now, g_vis, rep, spo, media_ids):
        PostQ.put((exe_toot,(toot_now, g_vis, rep, spo, media_ids)))

    th = threading.Timer(interval=interval,function=qput,args=(toot_now, g_vis, rep, spo, media_ids))
    th.start()

def exe_toot(toot_now, g_vis='direct', rep=None, spo=None, media_ids=None, interval=0):
    if spo:
        spo_len = len(spo)
    else:
        spo_len = 0
    if rep != None:
        try:
            # status = mastodon.status(rep)
            mastodon.status_post(status=toot_now[0:490-spo_len], visibility=g_vis, in_reply_to_id=rep, spoiler_text=spo, media_ids=media_ids)
        except Exception:
            sleep(2)
            mastodon.status_post(status=toot_now[0:490-spo_len], visibility=g_vis, in_reply_to_id=None, spoiler_text=spo, media_ids=media_ids)
    else:
        mastodon.status_post(status=toot_now[0:490-spo_len], visibility=g_vis, in_reply_to_id=None, spoiler_text=spo, media_ids=media_ids)

    # th = threading.Timer(interval=interval,function=th_toot,args=(toot_now, g_vis, rep, spo, media_ids))
    # th.start()
    jst_now = datetime.now(timezone('Asia/Tokyo'))
    ymdhms = jst_now.strftime("%Y%m%d %H%M%S")
    print("%s🆕toot:"%ymdhms + toot_now[0:300] + ":" + g_vis )

#######################################################
# ファボ処理
def fav_now(id):  # ニコります
    PostQ.put((exe_fav_now,(id,)))

def exe_fav_now(id):  # ニコります
    try:
        status = mastodon.status(id)
    except Exception as e:
        print(e)
    else:
        if status['favourited'] == False:
            #mastodon.status_favourite(id)
            th = threading.Timer(interval=2,function=mastodon.status_favourite,args=(id,))
            th.start()
            jst_now = datetime.now(timezone('Asia/Tokyo'))
            ymdhms = jst_now.strftime("%Y%m%d %H%M%S")
            print("%s🙆Fav"%ymdhms)

#######################################################
# アンケ回答
def enquete_vote(id,idx):
    PostQ.put((exe_enquete_vote,(id,idx)))

def exe_enquete_vote(id,idx):
    th = threading.Timer(interval=2,function=mastodon.vote,args=(id, idx))
    th.start()

#######################################################
# ブースト
def boost_now(id):  # ぶーすと！
    PostQ.put((exe_boost_now,(id,)))

def exe_boost_now(id):  # ぶーすと！
    try:
        status = mastodon.status(id)
    except Exception as e:
        print(e)
    else:
        if status['reblogged'] == False:
            mastodon.status_reblog(id)
        else:
            mastodon.status_unreblog(id)
            sleep(DELAY)
            mastodon.status_reblog(id)
        print("🙆boost")

#######################################################
# ブーキャン
def boocan_now(id):  # ぶーすと！
    PostQ.put((exe_boocan_now,(id,)))

def exe_boocan_now(id):  # ぶーすと！
    status = mastodon.status(id)
    if status['reblogged'] == True:
        mastodon.status_unreblog(id)
        print("🙆unboost")

#######################################################
# フォロー
def follow(id):
    PostQ.put((exe_follow,(id,)))

def exe_follow(id):
    mastodon.account_follow(id)
    # th = threading.Timer(interval=8,function=mastodon.account_follow,args=(id,))
    # th.start()
    print("♥follow")

#######################################################
# トゥー消し
def toot_delete(id,interval=5):
    def qput(id):
        PostQ.put((exe_toot_delete,(id,)))

    th = threading.Timer(interval=interval,function=qput,args=(id,))
    th.start()

def exe_toot_delete(id):
    mastodon.status_delete(id)
    print("♥toot delete")

#######################################################
# 数取りゲーム 投票前処理
def vote_check(status):
    acct = status["account"]["acct"]
    id = status["id"]
    if re.search(r'[^:]@%s'%BOT_ID, status['content']):
        if len(kiri_util.hashtag(status['content'])) > 0:
            return
        content = kiri_util.content_cleanser(status['content'])
        if len(content) == 0:
            return
        if acct == 'twotwo' and re.search(r'!', content):
            if len(GetNum_flg) > 0:
                twocnt = content.count('トゥ')
                GetNumVoteQ.put([acct, id, int(101 - twocnt)])
            else:
                toot('@%s\n₍₍ ◝(◍•ᴗ•◍)◟⁾⁾今は数取りゲームしてないよ〜'%acct, g_vis='unlisted', rep=id)
        else:
            if len(GetNum_flg) > 0:
                if content.strip().isdigit():
                    GetNumVoteQ.put([acct,id,int(content.strip())])
            else:
                if content.strip().isdigit():
                    toot('@%s\n₍₍ ◝(◍•ᴗ•◍)◟⁾⁾今は数取りゲームしてないよ〜'%acct, g_vis='unlisted', rep=id)

#######################################################
# ヒントでピント回答受付チェック
def HintPinto_ans_check(status):
    acct = status["account"]["acct"]
    id = status["id"]
    content = kiri_util.content_cleanser(status['content'])
    if len(content) == 0 or acct == BOT_ID:
        return
    if len(HintPinto_flg) > 0:
        HintPinto_ansQ.put([acct, id, content.strip()])

#######################################################
# 画像判定
def ana_image(media_attachments,sensitive,acct,g_vis,id,content):
    toot_now = ''
    #隠してある画像には反応しないことにしたー
    if sensitive:
        return toot_now

    for media in media_attachments[:1]:
        filename = download(media["url"] , "media")
        result = kiri_deep.takoramen(filename)
        print('   ',result)
        if result == 'other':
            if random.randint(0,50)  == 0:
                if face_search(filename,acct,g_vis,id):
                    return ''
                else:
                    pass
        elif result == '風景' or result == '夜景':
            if face_search(filename,acct,g_vis,id):
                return ''
            else:
                pass
        elif result == 'ねこ':
            toot_now += 'にゃーん'
        elif result == 'ダーツ':
            toot_now += '🎯ダーツ！'
        elif result == 'にじえろ':
            toot_now += 'えっち！'
        elif result == 'イラスト女の子':
            toot_now += 'かわいい！'
        elif result == 'イラスト男':
            toot_now += 'かっこいい！'
        elif result == 'イラスト線画':
            if '.mp' in filename or '.webm' in filename:
                pass
            else:
                r = random.randint(0,100)
                if r > 50:
                    coloring_image(filename,acct,g_vis,id)
                    return ''
                elif r > 30:
                    toot_now += '色塗ってー！'
        elif result == 'ろびすて':
            toot_now += '🙏ろびすてとうとい！'
        elif result == '漫画':
            toot_now += 'それなんて漫画ー？'
        elif result in  ['汚部屋','部屋','自撮り','太もも']:
            toot_now += result + 'だー！'
        elif result == 'ポプテピピック':
            toot_now += 'それポプテピピックー？'
        elif result == '電車':
            toot_now += '🚃🚃がたんごとん！'
        elif result == '真紅':
            toot_now += 'めいめいなのだわ！'
        elif result == '結月ゆかり':
            toot_now += 'ゆかりさん！'
        elif result == '真中らぁら':
            toot_now += 'かしこま！'
        elif result == '魂魄妖夢':
            toot_now += 'みょん！'
        elif result == '保登心愛':
            toot_now += 'こころぴょんぴょん！'
        elif result == '天々座理世':
            toot_now += 'こころぴょんぴょん！'
        elif result == '香風智乃':
            toot_now += 'チノちゃん！'
        elif result == '桐間紗路':
            toot_now += 'こころぴょんぴょん！'
        elif result == '宇治松千夜':
            toot_now += 'こころぴょんぴょん！'
        elif result == 'る':
            toot_now += 'インド人？'
        elif result == 'スクショ':
            if random.randint(0,4) == 0:
                toot_now += '📷スクショパシャパシャ！'
        else:
            if 'チョコ' in result or 'ショコラ' in result:
                toot_now += ':@%s: 🚓🚓🚓＜う〜う〜！飯テロ警察 チョコレート係でーす！\n'%(acct)
            else:
                toot_now += ':@%s: 🚓🚓🚓＜う〜う〜！飯テロ警察 %s係でーす！\n'%(acct,result)
            break

    return toot_now

#######################################################
# 着色サービス
def coloring_image(filename, acct, g_vis, id, color=None):
    media_files = []
    try:
        # tmp_file = painter.colorize(filename)
        tmp_file = kiri_deep.colorize(filename, color=color)
        result = kiri_deep.takoramen(tmp_file)
        if g_vis != 'direct' and result == 'にじえろ':
            toot_now = f"@{acct} えっち！"
        else:
            media_files.append(mastodon.media_post(tmp_file, 'image/png'))
            toot_now = f"@{acct} 色塗ったー！ \n#exp15m"
        toot(toot_now, g_vis=g_vis, rep=id, media_ids=media_files)
    except Exception as e:
        print(e)
        kiri_util.error_log()

#######################################################
# 顔マーク
def face_search(filename, acct, g_vis, id):
    media_files = []
    try:
        tmp = kiri_util.face_search(filename)
        if tmp:
            if tmp.rsplit('.')[-1] == 'jpg':
                ex = 'jpeg'
            else:
                ex = tmp.rsplit('.')[-1]
            media_files.append(mastodon.media_post(tmp, 'image/' + ex))
            toot_now = "@%s \n#exp15m"%acct
            toot(toot_now, g_vis=g_vis, rep=None, spo='おわかりいただけるだろうか……', media_ids=media_files, interval=5)
            return True
    except Exception as e:
        print(e)
        kiri_util.error_log()

#######################################################
# ワーカー処理の実装
def worker(status):
    id = status["id"]
    acct = status["account"]["acct"]
    username = "@" +  acct
    g_vis = status["visibility"]
    # if len(kiri_util.hashtag(status['content'])) > 0:
    #     return
    content = kiri_util.content_cleanser(status['content'])
    hashtags = kiri_util.hashtag(status['content'])
    if status['application'] == None:
        application = ''
    else:
        application = status['application']['name']
    statuses_count = status["account"]["statuses_count"]
    spoiler_text = status["spoiler_text"]
    ac_created_at = status["account"]["created_at"]
    ac_created_at = ac_created_at.astimezone(timezone('Asia/Tokyo'))
    ac_ymd = ac_created_at.strftime("%Y%m%d")
    jst_now = datetime.now(timezone('Asia/Tokyo'))
    now_ymd = jst_now.strftime("%Y%m%d")
    media_attachments = status["media_attachments"]
    sensitive = status['sensitive']
    enquete = None
    if status['enquete'] != None:
        enquete = json.loads(status['enquete'])

    rentou.append(acct)
    if len(rentou) > 20:
        rentou.pop(0)
    tmpcnt = sum([1 for x in rentou if x==acct]) 
    # 占有率50%超える人は異常なのでスルー
    if tmpcnt/len(rentou) > 0.5:
        return
    a = int(CM.get_coolingtime())
    rnd = random.randint(0,9+a+tmpcnt//5)
    if acct == MASTER_ID:
        rnd = 0

    #botはスルー
    botlist = set([tmp.strip() for tmp in open('.botlist').readlines()])

    if  acct in botlist:
        #bot例外
        if  acct == 'JC' and application != '女子会':
            pass
        elif  acct == '5' and 'TootIe' not in application:
            pass
        elif  acct == 'JC' and 'マストドン閉じろ' in content:
            pass
        elif acct == '12222222' and 'ふきふき' in content:
            pass
        # elif acct == 'hihobot': #仮対応。機能増えたら対処
        #     pass
        else:
            return

    if len(content) <= 0:
        return
    if  Toot1bQ.empty():
        content_1b, acct_1b = None,None
    else:
        content_1b, acct_1b = Toot1bQ.get() #キューから１回前を取得
    #
    Toot1bQ.put((content, acct))

    if re.search(r"^(緊急|強制)(停止|終了)$", content) and acct == MASTER_ID:
        print("＊＊＊＊＊＊＊＊＊＊＊緊急停止したよー！＊＊＊＊＊＊＊＊＊＊＊")
        toot("@%s 緊急停止しまーす！"%MASTER_ID, 'direct', id ,None)
        sleep(10)
        os.kill(os.getpid(), signal.SIGKILL)

    ############################################################
    # 定型文応答処理
    toot_now = ''
    id_now = id
    vis_now = g_vis
    interval = 0
    if re.search(r"(:nicoru[0-9]{0,3}:.?){4}", content):
        if content_1b != None and acct == acct_1b:
            if re.search(r"(:nicoru[0-9]{0,3}:.?){3}", content_1b):
                SM.update(acct, 'func')
                if rnd <= 8:
                    #toot_now = '　　三(  っ˃̵ᴗ˂̵) 通りまーす！'
                    toot_now = ':nicoru180: :nicoru180: :nicoru180: :nicoru180: :nicoru180: '
                    id_now = None
    elif re.search(r"(:nicoru[0-9]{0,3}:.?){2}", content):
        if content_1b != None and acct == acct_1b:
            if re.search(r"(:nicoru[0-9]{0,3}:.?){3}", content_1b):
                SM.update(acct, 'func')
                if rnd <= 8:
                    #toot_now = '　　(˃̵ᴗ˂̵っ )三 通りまーす！'
                    toot_now = ':nicoru180:'
                    id_now = None
    elif re.search(r"^貞$", content):
        if content_1b != None and acct == acct_1b:
            SM.update(acct, 'func',score=-1)
            if re.search(r"^治$", content_1b):
                SM.update(acct, 'func',score=2)
                if rnd <= 8:
                    toot_now = '　　三(  っ˃̵ᴗ˂̵) 通りまーす！'
                    id_now = None
    # elif acct == acct_1b:
    #     return

    #ネイティオが半角スペース区切りで５つ以上あれば翻訳
    if (acct == MASTER_ID or acct == 'twotwo') and len(content.split(' ')) > 4 and content.count('トゥ') > 4 and content.count('ー') > 0:
        toot_now = ':@%s: ＜「'%acct + kiri_util.two2jp(content) + '」'
        id_now = None
        SM.update(acct, 'func')
    if statuses_count != 0 and  statuses_count%10000 == 0:
        interval = 180
        toot_now = username + "\n"
        toot_now += "あ！そういえばさっき{0:,}トゥートだったよー！".format(statuses_count)
        id_now = None
        SM.update(acct, 'func')
    elif statuses_count == 1 and ac_ymd == now_ymd:
        interval = 5
        toot_now = username + "\n"
        toot_now += "新規さんいらっしゃーい！🍵🍡どうぞー！"
        vis_now = 'unlisted'
        SM.update(acct, 'func')
    elif re.search(r"草$", content+spoiler_text):
        SM.update(acct, 'func',score=-1)
        if rnd <= 1:
            # toot_now = ":" + username + ": "
            toot_now = random.choice(hanalist) #+ ' 三💨 ﾋﾟｭﾝ!!'
            id_now = None
    elif re.search(r"花$", content+spoiler_text):
        SM.update(acct, 'func')
        if rnd <= 1:
            tmp = []
            tmp.append('木')
            tmp.append('森')
            tmp.append('種')
            toot_now = random.choice(tmp)
            id_now = None
    elif re.search(r"^:twitter:.+🔥$", content, flags=(re.MULTILINE | re.DOTALL)):
        SM.update(acct, 'func')
        if rnd <= 4:
            tmp = []
            tmp.append(':twitter: ＜ﾊﾟﾀﾊﾟﾀｰ\n川\n\n🔥')
            tmp.append('(ﾉ・_・)ﾉ ﾆｹﾞﾃ!⌒:twitter: ＜ｱﾘｶﾞﾄｩ!\n🔥')
            tmp.append('(ﾉ・_・)ﾉ ﾆｹﾞﾃ!⌒🍗 ＜ｱﾘｶﾞﾄｩ!\n🔥')
            toot_now = random.choice(tmp)
            id_now = None
    elif re.search(r"ブリブリ|ぶりぶり|うん[ちこ]|💩", content+spoiler_text):
        SM.update(acct, 'func',score=-2)
        if rnd <= 4:
            tmp = []
            tmp.append( '🌊🌊🌊🌊 ＜ざばーっ！')
            tmp.append('( •́ฅ•̀ )ｸｯｻ')
            tmp.append('っ🚽')
            toot_now = random.choice(tmp)
            id_now = None
    elif re.search(r"^流して$|^水$", content+spoiler_text):
        SM.update(acct, 'func')
        if rnd <= 6:
            toot_now = '🌊🌊🌊🌊 ＜ざばーっ！'
            id_now = None
    elif re.search(r"^ふきふき$|^竜巻$|^風$", content):
        SM.update(acct, 'func')
        if rnd <= 4:
            tmp = []
            tmp.append('🌪🌪🌪🌪＜ごぉ〜〜っ！')
            tmp.append('💨💨💨🍃＜ぴゅ〜〜っ！')
            toot_now = random.choice(tmp)
            id_now = None
    elif re.search(r"^凍らせて$|^氷$", content):
        SM.update(acct, 'func')
        if rnd <= 2:
            toot_now = '❄❄❄❄❄＜カチコチ〜ッ！'
            id_now = None
    elif re.search(r"^雷$", content):
        SM.update(acct, 'func')
        if rnd <= 2:
            toot_now = '⚡️⚡️⚡️⚡️＜ゴロゴロ〜ッ！'
            id_now = None
    elif re.search(r"^ぬるぽ$|^[Nn]ull[Pp]ointer[Ee]xception$", content):
        SM.update(acct, 'func',score=-1)
        if rnd <= 4:
            toot_now = 'ｷﾘｯ'
            id_now = None
    elif re.search(r"^通過$", content):
        SM.update(acct, 'func')
        if rnd <= 6:
            tmp = []
            tmp.append('⊂(˃̵᎑˂̵๑⊃ )彡　阻止！')
            tmp.append('　ミ(  っ˃̵ᴗ˂̵)っ　阻止！')
            toot_now = random.choice(tmp)
            id_now = None
    elif re.search(r"3.{0,1}3.{0,1}4", content):
        SM.update(acct, 'func',score=-1)
        if rnd <= 6:
            toot_now = 'ﾅﾝ'
            id_now = None
    elif re.search(r"^ちくわ大明神$", content):
        SM.update(acct, 'func',score=-1)
        if rnd <= 6:
            toot_now = 'ﾀﾞｯ'
            id_now = None
    elif re.search(r"ボロン$|ぼろん$", content):
        SM.update(acct, 'func',score=-2)
        if rnd <= 2:
            toot_now = ':@%s: ✂️チョキン！！'%acct
            id_now = None
    elif re.search(r"さむい$|寒い$", content):
        SM.update(acct, 'func',score=-1)
        if rnd <= 2:
            toot_now = '🔥🔥🔥\n🔥:@%s:🔥\n🔥🔥🔥 '%acct
            id_now = None
    elif re.search(r"あつい$|暑い$", content):
        SM.update(acct, 'func',score=-1)
        if rnd <= 2:
            toot_now = '❄❄❄\n❄:@%s:❄\n❄❄❄ '%acct
            id_now = None
    elif re.search(r"^(今|いま)の[な|無|ナ][し|シ]$", content):
        SM.update(acct, 'func',score=-1)
        if rnd <= 4:
            toot_now = ':@%s: 🚓🚓🚓＜う〜う〜！いまのなし警察でーす！'%acct
            id_now = None
    elif re.search(r"ツイッター|ツイート|[tT]witter", content):
        SM.update(acct, 'func',score=-1)
        if rnd <= 1:
            toot_now = 'つ、つつつ、つい〜〜！！？！？？！？！'
            id_now = None
        elif rnd == 6:
            toot_now = 'つい〜……'
            id_now = None
    elif "きりちゃん" in content+spoiler_text or "ニコって" in content+spoiler_text:
        fav_now(id)
        SM.update(acct, 'reply')
    elif re.search(r"なんでも|何でも",content):
        SM.update(acct, 'func',score=-1)
        if rnd <= 2:
            toot_now = 'ん？'
            id_now = None
    elif re.search(r"泣いてる|泣いた|涙が出[るた(そう)]", content):
        SM.update(acct, 'func')
        if rnd <= 2:
            toot_now = '( *ˊᵕˋ)ﾉ:@%s: ﾅﾃﾞﾅﾃﾞ'%acct
            id_now = None
    elif re.search(r"^.+じゃないが$", content+spoiler_text):
        word = re.search(r"^(.+)じゃないが$", content+spoiler_text).group(1)
        SM.update(acct, 'func')
        if rnd <= 6 and len(word) < 10:
            toot_now = f'{word}じゃが！'
            id_now = None
    elif re.search(r"惚気|ほっけ|ホッケ", content+spoiler_text):
        SM.update(acct, 'func',score=-1)
        if rnd <= 2:
            toot_now = '🔥🔥🔥🔥＜ごぉぉぉっ！'
            id_now = None
    elif re.search(r"^燃やして$|^火$|^炎$", content+spoiler_text):
        SM.update(acct, 'func')
        if rnd <= 6:
            toot_now = '🔥🔥🔥🔥＜ごぉぉぉっ！'
            id_now = None
    elif "今日もみなさんが素敵な一日を送れますように" in content and acct == 'lamazeP':
        toot_now = '今み素一送！'
        id_now = None
        interval = random.uniform(0.01,0.7)
    elif re.search(r"[ご御夕昼朝][食飯][食た]べ[よるた]|(腹|はら)[へ減]った|お(腹|なか)[空す]いた|(何|なに)[食た]べよ", content):
        SM.update(acct, 'func')
        if rnd <= 3:
            recipe_service(content=content, acct=acct, id=id, g_vis=g_vis)
    elif re.search(r"^.+じゃね[ぇえ]ぞ", content+spoiler_text):
        word = re.search(r"^(.+)じゃね[ぇえ]ぞ", content+spoiler_text).group(1)
        SM.update(acct, 'func')
        if rnd <= 4 and len(word) <= 5:
            toot_now = f'{word}じゃぞ……💃'
            id_now = None
    elif re.search(r"止まるんじゃね[ぇえ]ぞ", content+spoiler_text):
        SM.update(acct, 'func')
        if rnd <= 4:
            toot_now = '止まるんじゃぞ……💃'
            id_now = None
    elif re.search(r"[おぉ][じぢ]|[おぉ][じぢ]さん", content+spoiler_text):
        SM.update(acct, 'func')
        if rnd <= 4:
            tmp = []
            tmp.append('٩(`^´๑ )۶三٩(๑`^´๑)۶三٩( ๑`^´)۶')
            tmp.append('٩(`^´๑ )۶三٩( ๑`^´)۶')
            tmp.append(' ₍₍ ٩(๑`^´๑)۶ ⁾⁾ぉぢぉぢダンスーー♪')
            tmp.append('٩(٩`^´๑ )三( ๑`^´۶)۶')
            toot_now = random.choice(tmp)
            id_now = None
    elif len(media_attachments) > 0 and re.search(r"色[ぬ塗]って", content) == None and re.search(r"きりぼ.*アイコン作", content) == None and re.search(r"きりぼ.*透過して", content) == None:
        toot_now = ana_image(media_attachments, sensitive, acct, g_vis, id_now, content)
        id_now = None
        interval = 0
    elif re.search(r"^う$", content):
        SM.update(acct, 'func')
        if rnd <= 6:
            toot_now = 'え'
            id_now = None
    elif re.search(r"^うっ$", content):
        SM.update(acct, 'func')
        if rnd <= 6:
            toot_now = 'えっ'
            id_now = None
    elif "マストドン閉じろ" in content:
        toot_now = 'はい'
        id_now = None
        interval = random.uniform(0.01,0.7)
    elif "(ง ˆᴗˆ)ว" in content:
        SM.update(acct, 'func')
        if rnd <= 6:
            toot_now = '◝( ・_・)◟ <ﾋﾟﾀｯ!'
            id_now = None
    elif re.search(r".+とかけまして.+と[と解]きます|.+とかけて.+と[と解]く$", content):
        SM.update(acct, 'func',score=2)
        toot_now = 'その心は？'
        id_now = None
        interval = 1
    elif re.search(r"^しばちゃんは.+[\?？]$", content) and acct in ['Ko4ba',MASTER_ID]:
        SM.update(acct, 'func')
        toot_now = '＼絶好調に美少女ー！／'
        interval = 1
        id_now = None
    elif re.search(r"^きりたんは.+[\?？]$", content) and acct == MASTER_ID:
        SM.update(acct, 'func')
        toot_now = '＼そこにいるー！／'
        interval = 1
        id_now = None
    elif re.search(r"^あのねあのね", content):
        if rnd <= 6:
            SM.update(acct, 'func')
            toot_now = 'なになにー？'
            interval = 0
            id_now = None
    elif re.search(r"パソコンつけ", content) and acct == "12":
            SM.update(acct, 'func')
            if rnd % 2 == 0:
                toot_now = '!お年玉'
            else:
                toot_now = '!おみくじ10連'
            interval = 8
            id_now = None
    else:
        nicolist = set([tmp.strip() for tmp in open('.nicolist').readlines()])
        if acct in nicolist:
            # rnd = random.randint(0,100)
            # if rnd % 4 == 0:
            fav_now(id_now)
    #
    if len(toot_now) > 0:
        toot(toot_now, vis_now, id_now, None, None, interval)
        return

    if re.search(r"死ね", content+spoiler_text):
        SM.update(acct, 'func',score=-20)
    if re.search(r"^クソ|クソ$|[^ダ]クソ", content+spoiler_text):
        SM.update(acct, 'func',score=-3)

    ############################################################
    #各種機能
    if re.search(r"きりぼ.*(しりとり).*(しよ|やろ|おねがい|お願い)", content):
        fav_now(id)
        if StMG.is_game(acct):
            toot('@%s 今やってる！\n※やめる場合は「しりとり終了」って言ってね'%acct, 'direct', id, None,interval=2)
            return

        StMG.add_game(acct)
        SM.update(acct, 'func')
        word1,yomi1,tail1 = StMG.games[acct].random_choice()
        result,text = StMG.games[acct].judge(word1)
        toot('@%s 【Lv.%d】じゃあ、%s【%s】の「%s」！\n※このトゥートにリプしてね！\n※DMでお願いねー！'%(acct,StMG.games[acct].lv,word1,yomi1,tail1) ,
                'direct',  id, None,interval=a)

    elif StMG.is_game(acct) and re.search(r"(しりとり).*(終わ|おわ|終了|完了)", content) and g_vis == 'direct':
        fav_now(id)
        toot('@%s おつかれさまー！\n(ラリー数：%d)'%(acct, StMG.games[acct].rcnt) , 'direct',  id, None,interval=a)
        StMG.end_game(acct)

    elif StMG.is_game(acct) and g_vis == 'direct':
        fav_now(id)
        word = str(content).strip()
        result,text = StMG.games[acct].judge(word)
        if result:
            if text == 'yes':
                ret_word,ret_yomi,tail = StMG.games[acct].get_word(word)
                if ret_word == None:
                    tmp_score = StMG.games[acct].rcnt*2+StMG.games[acct].lv
                    tmp_score //= 4
                    toot('@%s う〜ん！思いつかないよー！負けたー！\n(ラリー数：%d／%d点獲得)'%(acct,StMG.games[acct].rcnt,tmp_score), 'direct',  id, None,interval=a)
                    SM.update(acct, 'getnum', score=tmp_score)
                    StMG.end_game(acct)
                else:
                    result2,text2 = StMG.games[acct].judge(ret_word)
                    if result2:
                        toot('@%s %s【%s】の「%s」！\n(ラリー数：%d)\n※このトゥートにリプしてね！\n※DMでお願いねー！'%(acct, ret_word, ret_yomi, tail, StMG.games[acct].rcnt), 'direct',  id, None,interval=a)
                    else:
                        tmp_score = StMG.games[acct].rcnt+StMG.games[acct].lv
                        tmp_score //= 2
                        toot('@%s %s【%s】\n%sえ〜ん負けたー！\n(ラリー数：%d／%d点獲得)'%(acct, ret_word, ret_yomi,text2, StMG.games[acct].rcnt,tmp_score), 'direct',  id, None,interval=a)
                        SM.update(acct, 'getnum', score=tmp_score)
                        StMG.end_game(acct)

            else:
                #辞書にない場合
                toot('@%s %s\n※やめる場合は「しりとり終了」って言ってね！\n(ラリー数：%d)'%(acct,text, StMG.games[acct].rcnt), 'direct',  id, None,interval=a)
        else:
            toot('@%s %s\nわーい勝ったー！\n(ラリー数：%d)'%(acct, text, StMG.games[acct].rcnt), 'direct',  id, None,interval=a)
            StMG.end_game(acct)
    elif re.search(r"[!！]スロット", content) and g_vis == 'direct':
        fav_now(id)
        reelsize = 5
        if re.search(r"ミニ", content):
            slot_rate = 0.1
            reel_num = 4
        else:
            slot_rate = 1
            reel_num = 4

        #所持金チェック
        acct_score = SM.show(acct)[0][1]
        if acct_score < int(slot_rate*3):
            toot('@%s 得点足りないよー！（所持：%d点／必要：%d点）\nスロットミニや他のゲームで稼いでねー！'%(acct,acct_score,slot_rate*3), 'direct', rep=id,interval=a)
            return
        #貪欲補正
        slot_bal.append(acct)
        if len(slot_bal) > 100:
            slot_bal.pop(0)
        reelsize += min([sum([1 for x in slot_bal if x==acct])//10 , 5])
        #乱数補正
        reel_num += random.randint(-1,1)
        reelsize += random.randint(-1,1)
        reel_num = min([6,max([4,reel_num])])
        #得点消費
        SM.update(acct, 'getnum', score=- int(slot_rate*3))
        #スロット回転
        slot_accts = DAO.get_five(num=reel_num,minutes=120)
        slotgame = kiri_game.Friends_nico_slot(acct,slot_accts,slot_rate,reelsize)
        slot_rows,slot_score = slotgame.start()
        print(' '*20 + 'acct=%s reel_num=%d reelsize=%d'%(acct,reel_num,reelsize))
        sl_txt = ''
        for row in slot_rows:
            for c in row:
                sl_txt += c
            sl_txt += '\n'
        if slot_score > 0:
            SM.update(acct, 'getnum', score=slot_score)
            acct_score = SM.show(acct)[0][1]
            toot('@%s\n%s🎯当たり〜！！%d点獲得したよー！！（%d点消費／合計%d点）'%(acct, sl_txt, slot_score,int(slot_rate*3),acct_score), 'direct', rep=id, interval=a)
        else:
            acct_score = SM.show(acct)[0][1]
            toot('@%s\n%sハズレ〜〜（%d点消費／合計%d点）'%(acct, sl_txt ,int(slot_rate*3),acct_score), 'direct', rep=id, interval=a)

    elif re.search(r"(ヒントでピント)[：:](.+)", content):
        if g_vis == 'direct':
            word = re.search(r"(ヒントでピント)[：:](.+)", str(content)).group(2).strip()
            hintPinto_words = []
            if os.path.exists("hintPinto_words.txt"):
                for line in open('hintPinto_words.txt','r'):
                    hintPinto_words.append(line.strip())

            if word in hintPinto_words:
                toot(f'@{acct} この前やったお題なので別のにして〜！', 'direct', rep=id, interval=a)
                return

            hintPinto_words.append(word)
            if len(hintPinto_words) > 10:
                hintPinto_words.pop(0)

            with open('hintPinto_words.txt','w') as f:
                f.write("\n".join(hintPinto_words))

            HintPintoQ.put([acct,id,word])
            SM.update(acct, 'func')
        else:
            toot('@%s ＤＭで依頼してねー！周りの人に答え見えちゃうよー！'%acct, 'direct', rep=id, interval=a)
    elif enquete != None:
        if random.randint(0,4) == 0:
            if enquete['type'] == 'enquete':     #enquete_result
                x = len(enquete['items'])
                i = random.randrange(0,x-1)
                t = kiri_util.content_cleanser(enquete['items'][i])
                tmp = []
                tmp.append('う〜ん、やっぱ「%s」かなー'%t)
                tmp.append('断然「%s」だよねー！'%t)
                tmp.append('強いて言えば「%s」かもー？'%t)
                tmp.append('「%s」でいいや……'%t)
                toot_now = random.choice(tmp)
                enquete_vote(id, i)
                toot(toot_now, g_vis, None, None,interval=a*2)

    elif re.search(r"([ぼボ][とト][るル][メめ]ー[るル])([サさ]ー[ビび][スす])[：:]", content):
        print("★ボトルメールサービス")
        bottlemail_service(content=content, acct=acct, id=id, g_vis=g_vis)
        SM.update(acct, 'func')
    elif re.search(r"(きょう|今日)の.?(料理|りょうり)", content):
        recipe_service(content=content, acct=acct, id=id, g_vis=g_vis)
        SM.update(acct, 'func')
    elif re.search(r"\s?(.+)って(何|なに|ナニ|誰|だれ|ダレ|いつ|どこ)\?$", content):
        word = re.search(r"\s?(.+)って(何|なに|ナニ|誰|だれ|ダレ|いつ|どこ)\?$", str(content)).group(1)
        SM.update(acct, 'func')
        try:
            word = re.sub(r"きりぼ.*[、。]","",word)
            wikipedia.set_lang("ja")
            page = wikipedia.page(word)
        except  wikipedia.exceptions.DisambiguationError as e:
            toot('@%s 「%s」にはいくつか意味があるみたいだな〜'%(acct,word), g_vis, id, None, interval=a)
        except Exception as e:
            print(e)
            toot('@%s え？「%s」しらなーい！'%(acct,word), g_vis, id, None, interval=a)
        else:
            summary_text = page.summary
            if len(acct) + len(summary_text) + len(page.url) > 450:
                summary_text = summary_text[0:450-len(acct)-len(page.url)] + '……'
            toot('@%s %s\n%s'%(acct, summary_text, page.url), g_vis, id, 'なになに？「%s」とは……'%word, interval=a)

    elif len(media_attachments) > 0 and re.search(r"色[ぬ塗]って", content + spoiler_text):
        fav_now(id)
        for media in media_attachments:
            filename = download(media["url"] , "media")
            if '.mp' in filename or '.webm' in filename:
                pass
            else:
                if "赤" in content + spoiler_text:
                    colorvec = 0
                elif "青" in content + spoiler_text:
                    colorvec = 1
                elif "緑" in content + spoiler_text:
                    colorvec = 2
                elif "紫" in content + spoiler_text or "パープル" in content + spoiler_text:
                    colorvec = 3
                elif "茶" in content + spoiler_text or "ブラウン" in content + spoiler_text:
                    colorvec = 4
                elif "ピンク" in content + spoiler_text or "桃" in content + spoiler_text:
                    colorvec = 5
                elif "金" in content + spoiler_text or "黃" in content + spoiler_text:
                    colorvec = 6
                elif "白" in content + spoiler_text or "銀" in content + spoiler_text:
                    colorvec = 7
                elif "黒" in content + spoiler_text:
                    colorvec = 8
                else:
                    colorvec = None

                result = kiri_deep.takoramen(filename)
                if result in ["イラスト線画"]:
                    # 線画はそのまま塗る
                    coloring_image(filename,acct,g_vis,id, color=colorvec)
                else:
                    # それ以外は一旦線画に変換してから
                    line_path = kiri_util.image_to_line(filename)
                    coloring_image(line_path,acct,g_vis,id, color=colorvec)

    elif len(media_attachments) > 0 and re.search(r"きりぼ.*アイコン作", content):
        SM.update(acct, 'func', score=1)
        filename = download(media_attachments[0]["url"], "media")
        if re.search(r"正月", content):
            mode = 0
        elif re.search(r"2|２", content):
            mode = 2
        else:
            mode = 1

        ret = kiri_util.newyear_icon_maker(filename,mode=mode)
        if ret:
            media = mastodon.media_post(ret, 'image/gif')
            toot_now = f"@{acct} できたよ〜 \n ここでgifに変換するといいよ〜 https://www.aconvert.com/jp/video/mp4-to-gif/ \n#exp15m"
            toot(toot_now, g_vis=g_vis, rep=id, media_ids=[media])
        else:
            toot_now = f"@{acct} 透過画像じゃないとな〜"
            toot(toot_now, g_vis=g_vis, rep=id)

    elif len(media_attachments) > 0 and re.search(r"きりぼ.*透過して", content):
        SM.update(acct, 'func', score=1)
        filename = download(media_attachments[0]["url"], "media")
        alpha_image_path = kiri_util.auto_alpha(filename, icon=False)
        media = mastodon.media_post(alpha_image_path, 'image/png')
        toot_now = f"@{acct} できたよ〜 \n#exp15m"
        toot(toot_now, g_vis=g_vis, rep=id, media_ids=[media])

    elif re.search(r"([わワ][てテ]|拙僧|小職|私|[わワ][たタ][しシ]|[わワ][たタ][くク][しシ]|自分|僕|[ぼボ][くク]|俺|[オお][レれ]|朕|ちん|余|[アあ][タた][シし]|ミー|あちき|あちし|あたち|[あア][たタ][いイ]|[わワ][いイ]|わっち|おいどん|[わワ][しシ]|[うウ][ちチ]|[おオ][らラ]|儂|[おオ][いイ][らラ]|あだす|某|麿|拙者|小生|あっし|手前|吾輩|我輩|わらわ|ぅゅ|のどに|ちゃそ)の(ランク|ランキング|順位|スコア|成績|せいせき|らんく|らんきんぐ|すこあ)", content):
        show_rank(acct=acct, target=acct, id=id, g_vis=g_vis)
        SM.update(acct, 'func')
    elif re.search(r":@(.+):.*の(ランク|ランキング|順位|スコア|成績|せいせき|らんく|らんきんぐ|すこあ)", content):
        word = re.search(r":@(.+):.*の(ランク|ランキング|順位|スコア|成績|せいせき|らんく|らんきんぐ|すこあ)", str(content)).group(1)
        show_rank(acct=acct, target=word, id=id, g_vis=g_vis)
        SM.update(acct, 'func')
    elif re.search(r"(数取りゲーム|かずとりげぇむ).*(おねがい|お願い)", content):
        print('数取りゲーム受信')
        if len(GetNum_flg) > 0:
            toot("@%s 数取りゲーム開催中だよー！急いで投票してー！"%acct, 'public', id)
        else:
            fav_now(id)
            GetNumQ.put([acct,id])
            SM.update(acct, 'func')
    elif  '?トゥトゥトゥ' in content and acct == 'twotwo': #ネイティオ専用
        if len(GetNum_flg) > 0:
            toot("@%s 数取りゲーム開催中だよー！急いで投票してー！"%acct, 'public', id)
        else:
            GetNumQ.put([acct,id])
            SM.update(acct, 'func')
    elif len(content) > 140:
        cntdict = Counter(content)
        abclen = sum([v for k,v in cntdict.items() if k in abc])
        if len(content) * 0.8 < abclen:
            fav_now(id)
            lang = TRANS.detect(content)
            if lang and lang != 'ja':
                toot_now = TRANS.xx2ja(lang, content)
                if toot_now:
                    if re.search(r"[^:]@|^@", toot_now):
                        pass
                    else:
                        toot_now +=  "\n#きり翻訳 #きりぼっと"
                        toot(toot_now, 'public', id, '翻訳したよ〜！なになに……？ :@%s:＜'%acct ,interval=a)
                        SM.update(acct, 'func')
    elif  '翻訳して' in spoiler_text:
        fav_now(id)
        toot_now = TRANS.ja2en(content)
        if toot_now:
            if re.search(r"[^:]@|^@", toot_now):
                pass
            else:
                toot_now +=  "\n#きり翻訳 #きりぼっと"
                toot(toot_now, 'public', id, '翻訳したよ〜！ :@%s:＜'%acct ,interval=a)
                SM.update(acct, 'func')
    elif len(content) > 140 and (spoiler_text == None or spoiler_text == ''):
        content = re.sub(r"(.){3,}",r"\1",content, flags=(re.DOTALL))
        gen_txt = Toot_summary.summarize(pat1.sub("",pat2.sub("",content)),limit=10,lmtpcs=1, m=1, f=4)
        if gen_txt[-1] == '#':
            gen_txt = gen_txt[:len(gen_txt)-1]
        print('★要約結果：',gen_txt)
        if is_japanese(gen_txt):
            if len(gen_txt) > 5:
                gen_txt +=  "\n#きり要約 #きりぼっと"
                toot("@" + acct + " :@" + acct + ":\n"  + gen_txt, g_vis, id, "勝手に要約サービス", interval=a)
    elif re.search(r"チノチャレンジしてー", content + spoiler_text):
        paint_chino()
    elif re.search(r'[^:]@%s'%BOT_ID, status['content']):
        SM.update(acct, 'reply')
        if content.strip().isdigit():
            return
        if len(content) == 0:
            return
        rep_cnt.append(acct)
        toots_for_rep[acct].append(content)
        if len(toots_for_rep[acct]) > 20:
            toots_for_rep[acct].pop(0)
        if len(rep_cnt) > 30:
            rep_cnt.pop(0)
        tmpcnt = sum([1 for x in rep_cnt if x==acct]) 
        if tmpcnt > 20:
            return
        fav_now(id)
        toot_now = "@%s\n"%acct
        seeds = DAO.get_least_10toots()
        seeds.extend(toots_for_rep[acct])
        tmp = kiri_deep.lstm_gentxt(seeds,num=1)
        tmp = kiri_util.content_cleanser_light(tmp)
        # toots_for_rep[acct].append(tmp)
        # if len(toots_for_rep[acct]) > 20:
        #     toots_for_rep[acct].pop(0)
        toot_now += tmp
        toot(toot_now, g_vis, id, None,interval=a)
    elif re.search(r"(きり|キリ).*(ぼっと|ボット|[bB][oO][tT])|[きキ][りリ][ぼボ]", content + spoiler_text):
        SM.update(acct, 'reply')
        if random.randint(0,10+a) > 9:
            return
        fav_now(id)
        toot_now = "@%s\n"%acct
        seeds = DAO.get_least_10toots()
        tmp = kiri_deep.lstm_gentxt(seeds,num=1)
        tmp = kiri_util.content_cleanser_light(tmp)
        toot_now += tmp
        toot(toot_now, g_vis, id, None,interval=a)
        SM.update(acct, 'reply')

#######################################################
# 即時応答処理ー！
def business_contact(status):
    id = status["id"]
    acct = status["account"]["acct"]
    g_vis = status["visibility"]
    content = kiri_util.content_cleanser(status['content'])
    statuses_count = status["account"]["statuses_count"]
    spoiler_text = status["spoiler_text"]
    created_at = status['created_at']
    display_name = status["account"]['display_name']
    ac_created_at = status["account"]["created_at"]
    ac_created_at = ac_created_at.astimezone(timezone('Asia/Tokyo'))
    ac_ymd = ac_created_at.strftime("%Y.%m.%d %H:%M:%S")
    #最後にトゥートしてから3時間以上？ 
    if acct in acct_least_created_at:
        ymdhms = acct_least_created_at[acct]
    else:
        ymdhms = DAO.get_least_created_at(acct)

    acct_least_created_at[acct] = created_at
    diff = timedelta(hours=3)

    jst_now = datetime.now(timezone('Asia/Tokyo'))
    jst_now_str = jst_now.strftime("%Y%m%d %H%M%S")
    print('%s===「%s」by %s'%(jst_now_str,('\n'+' '*20).join(content.split('\n')), acct))

    if statuses_count == 1:
        fav_now(id)
        toot_now = '@%s 新規さんかも−！\n:@%s:(%s)＜「%s」(created at %s)\n#exp10m'%(MASTER_ID, acct, display_name, content, ac_ymd)
        toot(toot_now, rep=id)

        # toot_now = ':@%s: （%s）ご新規さんかもー！(๑•᎑•๑)♬*゜\n #ももな代理 #ニコフレ挨拶部 #しんかこ'%(acct,display_name)
        # toot(toot_now, g_vis='public',interval=3)
    elif ymdhms == None or ymdhms + diff < created_at:
        fav_now(id)
        # toot_now = '@%s 帰ってきたよ−！(前回書込：%s)\n:@%s:(%s)＜「%s」'%(MASTER_ID, ymdhms.strftime("%Y.%m.%d %H:%M:%S"), acct, display_name, content)
        # toot(toot_now, rep=id)

        # toot_now = ':@%s: %s!おかえりー！(๑́ºㅿº๑̀)💦\n #ももな代理 #ニコフレ挨拶部'%(acct,display_name)
        # toot(toot_now, g_vis='public',interval=3)

    pita_list.append(created_at)
    if len(pita_list) > 1:
        pita_list.pop(0)

    watch_list = set([kansi_acct.strip() for kansi_acct in open('.watch_list').readlines()])
    if acct in watch_list:
        toot_now = '@%s\n:@%s: %s\n「%s」\n#exp10m'%(MASTER_ID, acct, display_name, content)
        toot(toot_now)

#######################################################
# 画像検索サービス
def get_file_name(url):
    return url.split("/")[-1]

def download(url, save_path):
    ret_path = save_path + "/" + get_file_name(url)
    if os.path.exists(ret_path):
        return ret_path
    req = urllib.request.Request(url)
    req.add_header("User-agent", "kiritan downloader made by @kiritan")
    source = urllib.request.urlopen(req).read()
    with open(ret_path, 'wb') as file:
        file.write(source)
    return ret_path

#######################################################
# 日本語っぽいかどうか判定
def is_japanese(string):
    for ch in string:
        name = unicodedata.name(ch,"other")
        if "CJK UNIFIED" in name  or "HIRAGANA" in name  or "KATAKANA" in name:
            return True
    return False

#######################################################
# レシピ提案
def recipe_service(content=None, acct=MASTER_ID, id=None, g_vis='unlisted'):
    # print('recipe_service parm ',content, acct, id, g_vis)
    fav_now(id)
    generator = GenerateText.GenerateText(1)
    #料理名を取得ー！
    gen_txt = ''
    spoiler = generator.generate("recipe")
    # print('料理名：%s'%spoiler)

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
    generator = GenerateText.GenerateText(50)
    while len(text_chu) <= 3 or len(text_end) < 1:
        tmp_texts = generator.generate("recipe_text").split('\n')
        for tmp_text in tmp_texts:
            #print('料理のレシピ：%s'%tmp_text)
            if re.search(r'完成|出来上|召し上が|できあがり|最後|終わり',tmp_text):
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
# ランク表示
def show_rank(acct=None, target=None, id=None, g_vis=None):
    ############################################################
    # 数取りゲームスコアなど
    if id:
        fav_now(id)
    sm = kiri_util.ScoreManager()
    score = defaultdict(int)
    like = defaultdict(int)

    for row in sm.show():
        # if row[1] > 0:
        score[row[0]] = row[1]
        like[row[0]] = row[2] + row[4] + row[6] + row[7]

    if acct:
        score_rank = 0
        for i,(k,v) in enumerate( sorted(score.items(), key=lambda x: -x[1])):
            if k == target :
                score_rank = i + 1
                break

        like_rank = 0
        for i,(k,v) in enumerate( sorted(like.items(), key=lambda x: -x[1])):
            if k == target :
                like_rank = i + 1
                break

        toot_now = "@{0}\n:@{1}: のスコアは……\n".format(acct,target)
        toot_now += "ゲーム得点：{0:>4}点({1}/{4}位)\nきりぼっと好感度：{2:>4}点({3}/{5}位)".format(score[target], score_rank, like[target], like_rank, len(score), len(like))

        hours=[1,24] #,24*31]
        coms=["時間","日　"]  #,"ヶ月"]
        for hr,com in zip(hours,coms):
            rank = 0
            cnt = 0
            rows = DAO.get_toots_hours(hours=hr)
            rows.sort(key=lambda x:(-x[1],x[0]))
            for i,(k,v) in enumerate(rows):
                if k == target :
                    rank = i + 1
                    cnt = v
                    break
            toot_now += "\n直近１{1}：{0:,} toots（{2}/{3}位）".format(cnt,com,rank,len(rows))

        toot(toot_now, g_vis ,id, interval=2)

    else:
        toot_now = "■ゲーム得点\n"
        spo_text = "きりぼゲーム＆好感度ランキング"
        for i, (k, v) in enumerate(sorted(score.items(), key=lambda x: -x[1])):
            toot_now += f"{i+1}位 :@{k}: {v}点\n"
            if i >= 9:
                break

        toot_now += "\n■好感度\n"
        for i, (k, v) in enumerate(sorted(like.items(), key=lambda x: -x[1])):
            toot_now += f"{i+1}位 :@{k}: {v}点\n"
            if i >= 9:
                break

        toot(toot_now, g_vis='private', spo=spo_text, interval=2)

#######################################################
# チノチャレンジ
def paint_chino():
    img_path = kiri_deep.make_chino()
    media = mastodon.media_post(img_path, 'image/png')
    toot_now = f"#きりぼのチノチャレンジ #exp15m"
    toot(toot_now, g_vis="unlisted", media_ids=[media])

#######################################################
# ボトルメールサービス　メッセージ登録
def bottlemail_service(content, acct, id, g_vis):
    fav_now(id)
    word = re.search(r"([ぼボ][とト][るル][メめ]ー[るル])([サさ]ー[ビび][スす])[：:](.*)", str(content), flags=(re.MULTILINE | re.DOTALL) ).group(3)
    toot_now = "@" + acct + "\n"
    if len(word) == 0:
        toot(toot_now + "₍₍ ◝(* ,,Ծ‸Ծ,, )◟ ⁾⁾メッセージ入れてー！", g_vis ,id,None)
        return
    if len(word) > 300:
        toot(toot_now + "₍₍ ◝(* ,,Ծ‸Ծ,, )◟ ⁾⁾長いよー！", g_vis ,id,None)
        return

    bm = bottlemail.Bottlemail()
    bm.bottling(acct,word,id)

    spoiler = "ボトルメール受け付けたよー！"
    toot_now += "受け付けたメッセージは「" + word + "」だよー！いつか届くから気長に待っててねー！"
    toot(toot_now, g_vis , id, spoiler)

#######################################################
# ワーカー処理のスレッド
def th_worker():
    try:
        while True:
            status = WorkerQ.get() #キューからトゥートを取り出すよー！なかったら待機してくれるはずー！
            worker(status)
    except Exception as e:
        print(e)
        kiri_util.error_log()
        sleep(30)
        th_worker()

#######################################################
# ワーカー処理のスレッド
def th_timerDel():
    try:
        while True:
            status = TimerDelQ.get() #キューからトゥートを取り出すよー！なかったら待機してくれるはずー！
            id = status["id"]
            acct = status["account"]["acct"]
            hashtags = kiri_util.hashtag(status['content'])

            if acct == BOT_ID:
                sec = 0
                for hashtag in hashtags:
                    if hashtag[:3] == "exp" and hashtag[3:-1].isdigit():
                        time = int(hashtag[3:-1])
                        if hashtag[-1] == "s":
                            pass
                        elif hashtag[-1] == "m":
                            time *= 60
                        elif hashtag[-1] == "h":
                            time *= 60 * 60
                        elif hashtag[-1] == "d":
                            time *= 60 * 60 * 24
                        else:
                            time = 0
                        sec += time
                if sec > 0:
                    toot_delete(id=id, interval=sec)

    except Exception as e:
        print(e)
        kiri_util.error_log()
        sleep(30)
        th_timerDel()


#######################################################
# 陣形
def jinkei_tooter():
    spoiler = "勝手に陣形サービス"
    gen_txt = kiri_romasaga.gen_jinkei()
    # gen_txt = '@kiritan\n' + gen_txt
    toot(gen_txt, "public", spo=spoiler)

#######################################################
# ボトルメールサービス　配信処理
def bottlemail_sending():
    bm = bottlemail.Bottlemail()
    sendlist = bm.drifting()
    for id,acct,msg,reply_id in sendlist:
        spoiler = ":@" + acct + ": から🍾ボトルメール💌届いたよー！"
        random_acct = DAO.sample_acct()
        #お届け！
        toots = "@" + random_acct + "\n:@" + acct + ":＜「" + msg + "」"
        toots +=  "\n※ボトルメールサービス：＜メッセージ＞　であなたも送れるよー！試してみてね！"
        toots +=  "\n#ボトルメールサービス #きりぼっと"
        toot(toots, "direct",reply_id if reply_id != 0 else None, spoiler)
        bm.sended(id, random_acct)

        #到着通知
        spoiler = ":@" + random_acct + ": が🍾ボトルメール💌受け取ったよー！"
        toots = "@" + acct + " 届けたメッセージは……\n:@" + acct + ": ＜「" + msg + "」"
        toots +=  "\n#ボトルメールサービス #きりぼっと"
        toot(toots, "direct",reply_id if reply_id != 0 else None, spoiler)

#######################################################
# きりぼっとのつぶやき
def lstm_tooter():
    seeds = DAO.get_least_10toots()
    if len(seeds) <= 2:
        return
    spoiler = None

    gen_txt = kiri_deep.lstm_gentxt(seeds,num=1)
    gen_txt = kiri_util.content_cleanser_light(gen_txt)
    if gen_txt[0:1] == '。':
        gen_txt = gen_txt[1:]
    if len(gen_txt) > 60:
        spoiler = ':@%s: 💭'%BOT_ID

    toot(gen_txt, "public", None, spoiler)

#######################################################
# DELETE時の処理
def th_delete():
    del_accts = []
    while True:
        try:
            toot_now = '@%s \n'%MASTER_ID
            row = DAO.pickup_1toot(DelQ.get())
            # 垢消し時は大量のトゥー消しが来るので、キューが溜まってる場合はスキップするよ〜
            if DelQ.qsize() >= 3:
                continue
            print('th_delete:',row)
            if row:
                acct = row[0]
                if acct not in del_accts and acct != BOT_ID:
                    date = '{0:08d}'.format(row[2])
                    time = '{0:06d}'.format(row[3])
                    ymdhms = '%s %s'%(date,time)
                    ymdhms = dateutil.parser.parse(ymdhms).astimezone(timezone('Asia/Tokyo'))
                    toot_now += ':@%s: 🚓🚓🚓＜う〜う〜！トゥー消し警察でーす！\n'%row[0]
                    toot_now += ':@%s: ＜「%s」 at %s\n#exp10m'%(row[0], kiri_util.content_cleanser(row[1]) , ymdhms.strftime("%Y.%m.%d %H:%M:%S"))
                    toot(toot_now, 'direct', rep=None, spo=':@%s: がトゥー消ししたよー……'%row[0], media_ids=None, interval=0)
                    SM.update(row[0], 'func', score=-1)
                    sleep(0.2)

                del_accts.append(acct)
                if len(del_accts) > 3:
                    del_accts.pop(0)

        except Exception as e:
            print(e)
            kiri_util.error_log()
            # sleep(30)
            # th_delete()

#######################################################
# ヒントでピントゲーム
def th_hint_de_pinto(gtime=20):
    def th_shududai(acct,id,term):
        paths = gi.get_images_forQ(term)
        # paths = kiri_util.fetch_and_save_img(term)
        if len(paths) > 0:
            path = random.choice(paths)
        else:
            toot('@%s 画像が見つからなかったー！'%acct, g_vis='direct', rep=id)
            junbiTM.reset(0)
            return
        img = Image.open(path).convert('RGB')
        if path.rsplit('.')[-1] == 'jpg':
            ex = 'jpeg'
        else:
            ex = path.rsplit('.')[-1]

        y = int(img.height/10)
        loop = 0
        hint_text = "なし"
        mask_map = [i for i in range(len(term))]
        for i in range(y,1,- int(y*3/10)):
            if len(break_flg) == 0:
                tmp = img.resize((int(img.width/i), int(img.height/i)),Image.NEAREST)  #LANCZOS BICUBIC NEAREST
                tmp = tmp.resize((img.width, img.height),Image.NEAREST)
                filename = path.split('.')[0] + '_{0}.png'.format(y)
                tmp.save(filename, "png")
                media_files = []
                media_files.append(mastodon.media_post(filename, 'image/' + ex))
                toot_now = "さて、これは何/誰でしょうか？\nヒント：{0}\n#きりたんのヒントでピント #exp15m".format(hint_text)
                toot(toot_now, g_vis='private', rep=None, spo=None, media_ids=media_files)
                for tt in range(60):
                    sleep(1)
                    if len(break_flg) > 0:
                        break
            else:
                break

            loop += 1
            loop_cnt.append(loop)
            if loop == 1:
                hint_text = "○"*len(term)
            elif len(term) > loop - 1:
                # hint_text = term[0:loop-1] + "○"*(len(term) - (loop-1))
                random.shuffle(mask_map)
                mask_map.pop()
                hint_text = ""
                for i,c in enumerate(term):
                    if i in mask_map:
                        hint_text += "○"
                    else:
                        hint_text += c

        # sleep(1)
        media_files = []
        media_files.append(mastodon.media_post(path, 'image/' + ex))
        toot_now = "正解は{0}でした〜！\n（出題 :@{1}: ） #exp15m".format(term,acct)
        toot(toot_now, g_vis='private', rep=None, spo=None, media_ids=media_files,interval=4)

    # gi = kiri_util.get_images(BING_KEY)
    gi = kiri_util.get_images_GGL(GOOGLE_KEY,GOOGLE_ENGINE_KEY)
    junbiTM = kiri_util.KiriTimer(30*60)
    junbiTM.reset(gtime*60)
    junbiTM.start()
    while True:
        tmp_list = HintPintoQ.get()
        g_acct,g_id,term = tmp_list[0], tmp_list[1], tmp_list[2]

        if junbiTM.check() > 0:
            sleep(3)
            remaintm = junbiTM.check()
            toot('@%s\n開催準備中だよー！あと%d分%d秒待ってねー！'%(g_acct,remaintm//60,remaintm%60), 'direct', g_id, None)
            sleep(27)
            continue

        HintPinto_flg.append('ON')
        break_flg = []
        loop_cnt = []
        th = threading.Thread(target=th_shududai, args=(g_acct,g_id,term))
        th.start()
        while True:
            tmp_list = HintPinto_ansQ.get()
            acct, id, ans = tmp_list[0], tmp_list[1], tmp_list[2]
            # print('ans=',ans)
            if not th.is_alive():
                break
            if g_acct != acct and term in ans:
                loop = len(loop_cnt)
                score = min([10,len(term)])*8//(2**loop)
                toot(':@{0}: 正解〜！'.format(acct), g_vis='private', rep=None, spo=None)
                SM.update(acct, 'getnum', score=score//1)
                SM.update(g_acct, 'getnum', score=score//2)
                break_flg.append('ON')
                toot('正解者には{0}点、出題者には{1}点入るよー！'.format(score//1, score//2), g_vis='private', rep=None, spo=None, interval=8)

                break

        th.join()
        #ゲーム終了後、次回開始までの準備期間
        HintPinto_flg.remove('ON')
        junbiTM.reset()
        junbiTM.start()

#######################################################
# 数取りゲーム
def th_gettingnum(gtime=30):
    gamenum = 100
    junbiTM = kiri_util.KiriTimer(60*60)
    junbiTM.reset(gtime*60)
    junbiTM.start()
    gameTM = kiri_util.KiriTimer(240)
    while True:
        try:
            g_acct,g_id = GetNumQ.get()
            if junbiTM.check() > 0:
                remaintm = junbiTM.check()
                toot('@%s\n開催準備中だよー！あと%d分%d秒待ってねー！'%(g_acct,remaintm//60,remaintm%60), 'unlisted', g_id, None)
                continue

            #アクティブ人数確認
            i = DAO.get_gamenum()
            if  i <= 10:
                toot('@%s\n人少ないからまた後でねー！'%g_acct, 'unlisted', g_id, None)
                continue

            #ゲーム開始ー！
            fav_now(g_id)
            gm = kiri_game.GettingNum(gamenum)
            gameTM.reset()
            gameTM.start()
            toot('🔸1〜%dの中から誰とも被らない最大の整数に投票した人が勝ちだよー！\
                    \n🔸きりぼっとにメンション（ＤＭ可）で投票してね！\
                    \n🔸制限時間は%d分だよー！はじめ！！\n#数取りゲーム #きりぼっと'%(gamenum,int(gameTM.check()/60)), 'public', None, '💸数取りゲーム（ミニ）始まるよー！🎮')
            GetNum_flg.append('ON')
            try:
                #残り１分処理
                remaintm = gameTM.check()
                toot('数取りゲーム（ミニ）残り１分だよー！(1〜%d)\
                \n#数取りゲーム #きりぼっと'%(gamenum,), 'public',interval=remaintm - 60)
                while True:
                    remaintm = gameTM.check()
                    if remaintm > 0:
                        #時間切れは例外で抜ける
                        acct,id,num = GetNumVoteQ.get(timeout=remaintm)
                        if gm.vote(acct,num):
                            fav_now(id)
                            if  acct == 'twotwo':
                                toot('@%s\n%dだねー！わかったー！'%(acct,num), 'direct', id, None)
                        else:
                            toot('@%s\n٩(๑`^´๑)۶範囲外だよー！'%acct, 'direct', id, None)
                    else:
                        #時間切れ
                        break
            except queue.Empty:
                pass
            #ゲーム終了後、次回開始までの準備期間
            GetNum_flg.remove('ON')
            junbiTM.reset()
            junbiTM.start()
            results = gm.get_results()
            if sum( list(map(len,results.values())) ) <= 0:
                toot('(ง •̀ω•́)ง✧数取りゲーム、０人だったよー！\n#数取りゲーム #きりぼっと', 'public', None, None)
            else:
                toot_now = ''
                hanamaru = False
                score = 0
                for val,accts in sorted(results.items(), key=lambda x: -x[0]):
                    if len(accts) == 0:
                        continue
                    elif len(accts) == 1 and not hanamaru:
                        toot_now += '💮'
                        hanamaru = True
                        # print('#######%sに%d点！'%(accts[0],val))
                        score = val
                        SM.update(accts[0], 'getnum', score=score)
                    else:
                        toot_now += '❌'

                    toot_now += '{0:>2}：'.format(val)
                    for acct1 in accts:
                        toot_now += ':@%s:'%acct1
                    toot_now += '\n'
                toot('%s\n得点は%d点だよー\n#数取りゲーム #きりぼっと'%(toot_now,score), 'public', None, '数取りゲーム、結果発表ーー！！')

        except Exception as e:
            print(e)
            kiri_util.error_log()

#######################################################
# トゥートをいろいろ
def th_saver():
    try:
        while True:
            status = StatusQ.get()
            # 業務連絡
            business_contact(status)
            # トゥートを保存
            try:
                # threading.Thread(target=DAO.save_toot, args=(status,))
                DAO.save_toot(status)
            except Exception as e:
                #保存失敗したら、キューに詰めてリトライ！
                print(e)
                kiri_util.error_log()
                sleep(2)
                StatusQ.put(status)
    except Exception as e:
        print(e)
        kiri_util.error_log()
        sleep(10)
        th_saver()

#######################################################
# ローカルタイムライン監視スレッド
def t_local():
    try:
        # mastodon.stream_public(ltl_listener())
        mastodon.stream_local(ltl_listener(),timeout=20)
    except requests.exceptions.ConnectionError as e:
        print("＊＊＊再接続するよ〜t_local()＊＊＊")
        # print(e)
        # kiri_util.error_log()
        sleep(5)
        t_local()
    except Exception as e:
        print(e)
        kiri_util.error_log()
        sleep(5)
        t_local()

#######################################################
# ローカルタイムライン監視スレッド（認証なし）
def t_sub():
    try:
        publicdon.stream_local(public_listener(),timeout=20)
    except requests.exceptions.ConnectionError as e:
        print("＊＊＊再接続するよ〜t_sub()＊＊＊")
        # print(e)
        # kiri_util.error_log()
        sleep(5)
        t_sub()
    except Exception as e:
        print(e)
        kiri_util.error_log()
        sleep(5)
        t_sub()

#######################################################
# ホームタイムライン監視スレッド
def t_user():
    try:
        mastodon.stream_user(notification_listener(),timeout=20)
    except requests.exceptions.ConnectionError as e:
        print("＊＊＊再接続するよ〜t_user()＊＊＊")
        # print(e)
        # kiri_util.error_log()
        sleep(5)
        t_user()
    except Exception as e:
        print(e)
        kiri_util.error_log()
        sleep(5)
        t_user()

#######################################################
# randomニコルくん
def th_nicoru():
    gen_txt = ''
    while len(gen_txt) < 430:
        gen_txt += ':nicoru{0}:'.format(random.randint(0,360))
    toot('@%s '%MASTER_ID + gen_txt, "direct", None, None)

#######################################################
# にゃんタイム
def nyan_time():
    gen_txt = 'にゃんにゃんにゃんにゃん！\n₍₍(ฅ=˘꒳ ˘=)ฅ ⁾⁾ ₍₍ ฅ(=╹꒳ ╹=ฅ)⁾⁾'
    toot(gen_txt, "public")

#######################################################
# フォロ外し
def th_follow_mente():
    print('🌠フォローフォロワー整理処理ーー！！')
    ret = mastodon.account_verify_credentials()
    uid = ret['id']
    sleep(2)
    ret = mastodon.account_following(uid, max_id=None, since_id=None, limit=80)
    fids = []
    for account in ret:
        fids.append(account['id'])
    while '_pagination_next' in ret[-1].keys():
        for account in ret:
            fids.append(account['id'])
        max_id = ret[-1]['_pagination_next']['max_id']
        sleep(2)
        ret = mastodon.account_following(uid, max_id=max_id, since_id=None, limit=80)
        for account in ret:
            fids.append(account['id'])
    print('　　フォロー：',len(fids))
    sleep(2)
    ret = mastodon.account_followers(uid, max_id=None, since_id=None, limit=80)
    fers = []
    for account in ret:
        fers.append(account['id'])
    while '_pagination_next' in ret[-1].keys():
        for account in ret:
            fers.append(account['id'])
        max_id = ret[-1]['_pagination_next']['max_id']
        sleep(2)
        ret = mastodon.account_followers(uid, max_id=max_id, since_id=None, limit=80)
        for account in ret:
            fers.append(account['id'])
    print('　　フォロワー：',len(fers))
    sleep(1)
    for u in set(fers) - set(fids):
        print('id=',u)
        try:
            mastodon.account_follow(u)
        except Exception as e:
            print('id=',u,e)
            kiri_util.error_log()
        sleep(2)
    for u in set(fids) - set(fers):
        print('id=',u)
        try:
            mastodon.account_unfollow(u)
        except Exception as e:
            print('id=',u,e)
            kiri_util.error_log()
        sleep(2)

#######################################################
# post用worker
def th_post():
    while True:
        try:
            func,args = PostQ.get()
            func(*args)
            sleep(2.0)
            # sleep(2.0+CM.get_coolingtime())
        except Exception as e:
            print(e)
            kiri_util.error_log()
            # sleep(10)
            # th_post()

#######################################################
# pita
def th_pita():
    while True:
        sleep(10.0)
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        diff = timedelta(seconds=60)
        # toot[-1] + 1min < now -> pita!
        if len(pita_list) > 0 and pita_list[-1] + diff < jst_now:
            toot('◝( ・_・)◟ <ﾋﾟﾀｯ!', g_vis='public')
            sleep(3600.0)

#######################################################
# メイン
def main():
    args = get_args()
    threads = []
    #タイムライン受信系
    threads.append( threading.Thread(target=t_local ) ) #LTL
    threads.append( threading.Thread(target=t_user ) ) #LTL
    threads.append( threading.Thread(target=t_sub ) ) #LTL
    #タイムライン応答系
    threads.append( threading.Thread(target=th_delete) )
    threads.append( threading.Thread(target=th_saver) )
    threads.append( threading.Thread(target=th_gettingnum, args=(args.gtime,)) )
    threads.append( threading.Thread(target=th_hint_de_pinto, args=(args.htime,)) )
    threads.append( threading.Thread(target=th_worker) )
    threads.append( threading.Thread(target=th_timerDel) )
    threads.append( threading.Thread(target=th_post) )
    threads.append( threading.Thread(target=th_pita) )
    #スケジュール起動系(時刻)
    # threads.append( threading.Thread(target=kiri_util.scheduler, args=(summarize_tooter,['**:02'])) )
    threads.append( threading.Thread(target=kiri_util.scheduler, args=(bottlemail_sending,['**:05'])) )
    threads.append( threading.Thread(target=kiri_util.scheduler, args=(th_follow_mente,['04:00'])) )
    threads.append( threading.Thread(target=kiri_util.scheduler, args=(nyan_time,['22:22'])) )
    threads.append( threading.Thread(target=kiri_util.scheduler, args=(show_rank,['07:00'])) )
    threads.append( threading.Thread(target=kiri_util.scheduler, args=(paint_chino,['05:30'])) )
    #スケジュール起動系(間隔)
    # threads.append( threading.Thread(target=kiri_util.scheduler_rnd, args=(monomane_tooter,120,0,15,CM)) )
    threads.append( threading.Thread(target=kiri_util.scheduler_rnd, args=(lstm_tooter,10,-3,2,CM)) )
    # threads.append( threading.Thread(target=kiri_util.scheduler_rnd, args=(timer_bst1st,90,0,15,CM)) )
    # threads.append( threading.Thread(target=kiri_util.scheduler_rnd, args=(th_nicoru,60,0,60,CM)) )
    # threads.append( threading.Thread(target=kiri_util.scheduler_rnd, args=(tangrkn_tooter,20,-10,10,CM)) )
    threads.append( threading.Thread(target=kiri_util.scheduler_rnd, args=(jinkei_tooter,120,-10,10,CM)) )

    for th in threads:
        th.start()
    # for th in threads:
    #     th.join()

if __name__ == '__main__':
    main()
