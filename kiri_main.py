# -*- coding: utf-8 -*-

from mastodon import Mastodon,StreamListener
import re, os, json, random, unicodedata, signal, sys
import threading, MeCab, queue, urllib
from time import sleep
from pytz import timezone
import dateutil
from datetime import datetime,timedelta
import warnings, traceback
from os.path import join, dirname
from dotenv import load_dotenv
import wikipedia
import Toot_summary, GenerateText, PrepareChain, bottlemail
import kiri_util, kiri_deep, kiri_game, kiri_coloring, kiri_romasaga
from PIL import Image, ImageOps, ImageFile, ImageChops, ImageFilter, ImageEnhance
ImageFile.LOAD_TRUNCATED_IMAGES = True

MASTER_ID = 'kiritan'
BOT_ID = 'kiri_bot01'
BOTS = [BOT_ID,'friends_booster','5','JC','12222222','bt']
DELAY = 2
pat1 = re.compile(r' ([!-~ぁ-んァ-ン] )+|^([!-~ぁ-んァ-ン] )+| [!-~ぁ-んァ-ン]$',flags=re.MULTILINE)  #[!-~0-9a-zA-Zぁ-んァ-ン０-９ａ-ｚ]
pat2 = re.compile(r'[ｗ！？!\?]')

#得点管理、流速監視
SM = kiri_util.ScoreManager()
CM = kiri_util.CoolingManager(5)
DAO = kiri_util.DAO_statuses()
painter = kiri_coloring.Painter(gpu=-1)
#しりとり用
StMG = kiri_game.Siritori_manager()


#.envファイルからトークンとかURLを取得ー！
dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)
MASTODON_URL = os.environ.get("MASTODON_URL")
MASTODON_ACCESS_TOKEN = os.environ.get("MASTODON_ACCESS_TOKEN")
BING_KEY = os.environ.get("BING_KEY")

publicdon = Mastodon(api_base_url=MASTODON_URL)  # インスタンス

mastodon = Mastodon(
    access_token=MASTODON_ACCESS_TOKEN,
    api_base_url=MASTODON_URL)  # インスタンス

PostQ = queue.Queue()
TQ = queue.Queue()
QQ = queue.Queue()
StatusQ = queue.Queue()
Toot1bQ = queue.Queue()
DelQ = queue.Queue()
GetNumQ = queue.Queue()
GetNumVoteQ = queue.Queue()
GetNum_flg = []
HintPintoQ = queue.Queue()
HintPinto_ansQ = queue.Queue()
HintPinto_flg = []

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

#######################################################
# マストドンＡＰＩ用部品を継承して、通知時の処理を実装ー！
class notification_listener(StreamListener):
    def on_notification(self, notification):
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        ymdhms = jst_now.strftime("%Y%m%d %H%M%S")
        print("%s===notification_listener on_notification==="%ymdhms)

        if notification["type"] == "mention":
            status = notification["status"]
            QQ.put(status)
            vote_check(status)
            TQ.put(status)
            SM.update(notification["status"]["account"]["acct"], 'reply')
        elif notification["type"] == "favourite":
            SM.update(notification["account"]["acct"], 'fav', ymdhms)
        elif notification["type"] == "reblog":
            SM.update(notification["account"]["acct"], 'boost', ymdhms)
        elif notification["type"] == "follow":
            SM.update(notification["account"]["acct"], 'boost', ymdhms)
            follow(notification["account"]["id"])
    def on_update(self, status):
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        ymdhms = jst_now.strftime("%Y%m%d %H%M%S")
        print("%s===notification_listener on_update==="%ymdhms)
        HintPinto_ans_check(status)

#######################################################
# マストドンＡＰＩ用部品を継承して、ローカルタイムライン受信時の処理を実装ー！
class ltl_listener(StreamListener):
    def on_update(self, status):
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        ymdhms = jst_now.strftime("%Y%m%d %H%M%S")
        print("%s===ltl_listener on_update==="%ymdhms)
        #mentionはnotificationで受けるのでLTLのはスルー！(｢・ω・)｢ 二重レス防止！
        if re.search(r'[^:]@' + BOT_ID, status['content']):
        #if  '@' + BOT_ID in status['content']:
            return
        if '@' in status["account"]["acct"]: #連合のトゥート
            if len(status["media_attachments"]) > 0:
                rnd = random.randint(0,1000)
                if rnd == 0:
                    status['content'] = ''
                    status['spoiler_text'] = ''
                    TQ.put(status)
            return
        else:
            TQ.put(status)
            QQ.put(status)

#######################################################
# タイムライン保存用（認証なし）
class public_listener(StreamListener):
    def on_update(self, status):
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        ymdhms = jst_now.strftime("%Y%m%d %H%M%S")
        print("%s===public_listener on_update==="%ymdhms)
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
    if rep != None:
        try:
            status = mastodon.status(rep)
        except Exception:
            mastodon.status_post(status=toot_now[0:450], visibility=g_vis, in_reply_to_id=None, spoiler_text=spo, media_ids=media_ids)
        else:
            mastodon.status_post(status=toot_now[0:450], visibility=g_vis, in_reply_to_id=rep, spoiler_text=spo, media_ids=media_ids)
    else:
        mastodon.status_post(status=toot_now[0:450], visibility=g_vis, in_reply_to_id=None, spoiler_text=spo, media_ids=media_ids)

    # th = threading.Timer(interval=interval,function=th_toot,args=(toot_now, g_vis, rep, spo, media_ids))
    # th.start()
    jst_now = datetime.now(timezone('Asia/Tokyo'))
    ymdhms = jst_now.strftime("%Y%m%d %H%M%S")
    print("%s🆕toot:"%ymdhms + toot_now[0:50] + ":" + g_vis )

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
    PostQ.put((boost_now,(id,)))

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
    PostQ.put((boocan_now,(id,)))

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
# 数取りゲーム 投票前処理
def vote_check(status):
    acct = status["account"]["acct"]
    id = status["id"]
    if re.search(r'[^:]@kiri_bot01', status['content']):
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
                toot('@%s\n₍₍ ◝(◍•ᴗ•◍)◟⁾⁾今は数取りゲームしてないよ〜'%acct, g_vis='unlisted', rep=id, interval=3)
        else:
            if len(GetNum_flg) > 0:
                if content.strip().isdigit():
                    GetNumVoteQ.put([acct,id,int(content.strip())])
            else:
                if content.strip().isdigit():
                    toot('@%s\n₍₍ ◝(◍•ᴗ•◍)◟⁾⁾今は数取りゲームしてないよ〜'%acct, g_vis='unlisted', rep=id, interval=3)

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

    for media in media_attachments:
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
            # if random.randint(0,9) > 0:
            #     coloring_image(filename,acct,g_vis,id)
            #     return ''
            # else:
            if random.randint(0,9) %4 == 0:
                toot_now += '色塗ってー！'
        elif result == 'ろびすて':
            toot_now += '🙏ろびすてとうとい！'
        elif result == '漫画':
            toot_now += 'それなんて漫画ー？'
        elif result in  ['汚部屋','部屋','自撮り','太もも']:
            toot_now += result + 'だー！'
        elif result == 'kent':
            toot_now += 'ケント丸だー！'
        elif result == 'ポプテピピック':
            toot_now += 'それポプテピピックー？'
        elif result == 'ボブ':
            toot_now += 'ボブだー！'
        elif result == 'ローゼンメイデン 真紅':
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
            toot_now += '■■■だー！'
        elif result == 'スクショ':
            if random.randint(0,4) == 0:
                toot_now += '📷スクショパシャパシャ！'
        elif sensitive:
            if 'ラーメン' in result or '麺' in result or result == 'うどん' or  result == 'そば':
                toot_now += '🍜%sちゅるちゅるーっ！'%result
            elif result == 'パスタ':
                toot_now += '🍝%sちゅるちゅるーっ！'%result
            elif 'バーガー' in result:
                toot_now += '🍔%sもぐもぐー！'%result
            elif result == 'からあげ':
                toot_now += 'かけるよね？っ🍋'
            elif result == 'サラダ':
                toot_now += '🥗さくさくー！'
            elif result == '冷凍チャーハン':
                toot_now += '焦がしにんにくのマー油と葱油が香るザ★チャーハン600g！？！？！？'
            elif result == '焼き鳥':
                toot_now += '鳥貴族ーー！！！！'
            elif result == 'ピザ':
                toot_now += 'ぽざ！'
            elif result == 'ビール':
                toot_now += '🍺しゅわしゅわ〜！'
            elif '緑茶' in result:
                toot_now += '🍵ずずーっ'
            elif '紅茶' in result or 'コーヒー' in result:
                toot_now += '☕ごくごく'
            elif 'チョコ' in result or 'ショコラ' in result:
                toot_now += 'チョコ系だー！おいしそう！'
            else:
                toot_now += result + 'だー！おいしそうー！'
        else:
            if 'チョコ' in result or 'ショコラ' in result:
                toot_now += ':@%s: 🚓🚓🚓＜う〜う〜！飯テロ警察 チョコレート係でーす！\n'%(acct)
            else:
                toot_now += ':@%s: 🚓🚓🚓＜う〜う〜！飯テロ警察 %s係でーす！\n'%(acct,result)
            break

    return toot_now

#######################################################
# 画像検索サービス
def coloring_image(filename, acct, g_vis, id):
    username = "@" +  acct
    media_files = []
    tmp_file = painter.colorize(filename)
    # tmp_file = kiri_deep.colorize(filename)
    try:
        result = kiri_deep.takoramen(tmp_file)
        if result == 'にじえろ':
            toot_now = "@%s えっち！"%acct
        else:
            media_files.append(mastodon.media_post(tmp_file, 'image/png'))
            toot_now = "@%s 色塗ったー！"%acct
        toot(toot_now, g_vis=g_vis, rep=id, media_ids=media_files)
    except Exception as e:
        print(e)
        kiri_util.error_log()

#######################################################
# 顔マーク
def face_search(filename, acct, g_vis, id):
    username = "@" +  acct
    media_files = []
    try:
        tmp = kiri_util.face_search(filename)
        if tmp:
            if tmp.rsplit('.')[-1] == 'jpg':
                ex = 'jpeg'
            else:
                ex = tmp.rsplit('.')[-1]
            media_files.append(mastodon.media_post(tmp, 'image/' + ex))
            toot_now = "@%s"%acct
            toot(toot_now, g_vis=g_vis, rep=None, spo='おわかりいただけるだろうか……', media_ids=media_files, interval=5)
            return True
    except Exception as e:
        print(e)
        kiri_util.error_log()

#######################################################
# 即時応答処理ー！
def quick_rtn(status):
    id = status["id"]
    acct = status["account"]["acct"]
    username = "@" +  acct
    g_vis = status["visibility"]
    # if len(kiri_util.hashtag(status['content'])) > 0:
    #     return
    content = kiri_util.content_cleanser(status['content'])
    if status['application'] == None:
        application = ''
    else:
        application = status['application']['name']
    # print('===%s\t「%s」'%(acct, '\n    '.join(content.split('\n'))))
    statuses_count = status["account"]["statuses_count"]
    spoiler_text = status["spoiler_text"]
    ac_created_at = status["account"]["created_at"]
    ac_created_at = ac_created_at.astimezone(timezone('Asia/Tokyo'))
    ac_ymd = ac_created_at.strftime("%Y%m%d")
    jst_now = datetime.now(timezone('Asia/Tokyo'))
    now_ymd = jst_now.strftime("%Y%m%d")
    media_attachments = status["media_attachments"]
    sensitive = status['sensitive']
    #botはスルー
    if  acct in BOTS:
        #ももながbotの場合もスルー
        if  acct == 'JC' and application != '女子会':
            pass
        elif  acct == 'JC' and 'マストドン閉じろ' in content:
            pass
        elif acct == '12222222' and 'ふきふき' in content:
            pass
        else:
            return
    if len(content) <= 0:
        return
    if  Toot1bQ.empty():
        content_1b, acct_1b, id_1b, g_vis_1b = None,None,None,None
    else:
        content_1b, acct_1b, id_1b, g_vis_1b = Toot1bQ.get() #キューから１回前を取得
    #
    Toot1bQ.put((content, acct, id, g_vis))

    if re.search(r"^(緊急|強制)(停止|終了)$", content) and acct == MASTER_ID:
        print("＊＊＊＊＊＊＊＊＊＊＊緊急停止したよー！＊＊＊＊＊＊＊＊＊＊＊")
        toot("@%s 緊急停止しまーす！"%MASTER_ID, 'direct', id ,None)
        sleep(10)
        os.kill(os.getpid(), signal.SIGKILL)

    a = int(CM.get_coolingtime())
    #a = int(a*a / 2)
    rnd = random.randint(0,10+a)
    if acct == MASTER_ID:
        rnd = 0
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
    elif toot_now == '' and acct == acct_1b:
        return

    #ネイティオが半角スペース区切りで５つ以上あれば翻訳
    if (acct == 'kiritan' or acct == 'twotwo') and len(content.split(' ')) > 4 and content.count('トゥ') > 4 and content.count('ー') > 0:
        toot_now = ':@%s: ＜「'%acct + kiri_util.two2jp(content) + '」'
        id_now = None
        SM.update(acct, 'func')
    elif statuses_count != 0 and  statuses_count%10000 == 0:
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
    elif re.search(r"^:twitter:.+🔥$", content, flags=(re.MULTILINE | re.DOTALL)):
        SM.update(acct, 'func')
        if rnd <= 4:
            tmp = []
            tmp.append(':twitter: ＜ﾊﾟﾀﾊﾟﾀｰ\n川\n\n🔥')
            tmp.append('(ﾉ・_・)ﾉ ﾆｹﾞﾃ!⌒:twitter: ＜ｱﾘｶﾞﾄｩ!\n🔥')
            tmp.append('(ﾉ・_・)ﾉ ﾆｹﾞﾃ!⌒🍗 ＜ｱﾘｶﾞﾄｩ!\n🔥')
            toot_now = random.choice(tmp)
            id_now = None
    elif re.search(r"ブリブリ|ぶりぶり|うん[ちこ]|💩|^流して$", content+spoiler_text):
        SM.update(acct, 'func',score=-2)
        if rnd <= 4:
            tmp = []
            tmp.append( '🌊🌊🌊🌊 ＜ざばーっ！')
            tmp.append('( •́ฅ•̀ )ｸｯｻ')
            tmp.append('っ🚽')
            toot_now = random.choice(tmp)
            id_now = None
    elif re.search(r"^ふきふき$|^竜巻$", content):
        SM.update(acct, 'func')
        if rnd <= 4:
            tmp = []
            tmp.append('🌪🌪🌪🌪＜ごぉ〜〜っ！')
            tmp.append('💨💨💨🍃＜ぴゅ〜〜っ！')
            toot_now = random.choice(tmp)
            id_now = None
    elif re.search(r"^凍らせて$", content):
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
    elif re.search(r"^はいじゃないが$", content+spoiler_text):
        SM.update(acct, 'func')
        if rnd <= 6:
            toot_now = 'はいじゃが！'
            id_now = None
    elif re.search(r"惚気|ほっけ|ホッケ|^燃やして$", content+spoiler_text):
        SM.update(acct, 'func',score=-1)
        if rnd <= 2:
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
    elif re.search(r"止まるんじゃね[ぇえ]ぞ", content+spoiler_text):
        SM.update(acct, 'func')
        if rnd <= 4:
            toot_now = '止まるんじゃぞ……💃'
            id_now = None
    elif re.search(r"[おぉ][じぢ]$|[おぉ][じぢ]さん", content+spoiler_text):
        SM.update(acct, 'func')
        if rnd <= 4:
            tmp = []
            tmp.append('٩(`^´๑ )۶三٩(๑`^´๑)۶三٩( ๑`^´)۶')
            tmp.append('٩(`^´๑ )۶三٩( ๑`^´)۶')
            tmp.append(' ₍₍ ٩(๑`^´๑)۶ ⁾⁾ぉぢぉぢダンスーー♪')
            tmp.append('٩(٩`^´๑ )三( ๑`^´۶)۶')
            toot_now = random.choice(tmp)
            id_now = None
    elif len(media_attachments) > 0 and re.search(r"色[ぬ塗]って", content) == None:
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
    elif re.search(r"マストドン閉じろ", content):
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
    else:
        nicolist = set([tmp.strip() for tmp in open('.nicolist').readlines()])
        if acct in nicolist:
            # rnd = random.randint(0,100)
            # if rnd % 4 == 0:
            fav_now(id_now)
    #
    if len(toot_now) > 0:
        toot(toot_now, vis_now, id_now, None, None, interval)

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
    ymdhms = DAO.get_least_created_at(acct)
    diff = timedelta(hours=3)
    jst_now = datetime.now(timezone('Asia/Tokyo'))
    jst_now_str = jst_now.strftime("%Y%m%d %H%M%S")
    print('%s===「%s」by %s'%(jst_now_str,'\n    '.join(content.split('\n')), acct))
    if ymdhms == None:
        toot_now = '@%s 新規さんかも−！\n:@%s:(%s)＜「%s」(created at %s)'%(MASTER_ID, acct, display_name, content, ac_ymd)
        toot(toot_now, rep=id)
        fav_now(id)

        # toot_now = ':@%s: （%s）ご新規さんかもー！(๑•᎑•๑)♬*゜\n #ももな代理 #ニコフレ挨拶部 #しんかこ'%(acct,display_name)
        # toot(toot_now, g_vis='public',interval=3)
    elif ymdhms + diff < created_at:
        # toot_now = '@%s 帰ってきたよ−！(前回書込：%s)\n:@%s:(%s)＜「%s」'%(MASTER_ID, ymdhms.strftime("%Y.%m.%d %H:%M:%S"), acct, display_name, content)
        # toot(toot_now, rep=id)

        # toot_now = ':@%s: %s!おかえりー！(๑́ºㅿº๑̀)💦\n #ももな代理 #ニコフレ挨拶部'%(acct,display_name)
        # toot(toot_now, g_vis='public',interval=3)
        fav_now(id)
        pass

    watch_list = set([kansi_acct.strip() for kansi_acct in open('.watch_list').readlines()])
    if acct in watch_list:
        toot_now = '@%s\n:@%s: %s\n「%s」'%(MASTER_ID, acct, display_name, content)
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
# ランク表示
def recipe_service(content=None, acct=MASTER_ID, id=None, g_vis='unlisted'):
    print('recipe_service parm ',content, acct, id, g_vis)
    fav_now(id)
    generator = GenerateText.GenerateText(1)
    #料理名を取得ー！
    gen_txt = ''
    spoiler = generator.generate("recipe")
    print('料理名：%s'%spoiler)

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
def show_rank(acct, target, id, g_vis):
    ############################################################
    # 数取りゲームスコアなど
    fav_now(id)
    sm = kiri_util.ScoreManager()
    score = {}
    like = {}
    users_ranking = {}

    for row in sm.show():
        # if row[1] > 0:
        score[row[0]] = row[1]
        like[row[0]] = row[2] + row[4] + row[6] + row[7]

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

    hours=[1,24,24*31]
    coms=["時間","日　","ヶ月"]
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

#######################################################
# ボトルメールサービス　メッセージ登録
def bottlemail_service(content, acct, id, g_vis):
    fav_now(id)
    word = re.search(r"([ぼボ][とト][るル][メめ]ー[るル])([サさ]ー[ビび][スす])[：:](.*)", str(content), flags=(re.MULTILINE | re.DOTALL) ).group(3)
    toot_now = "@" + acct + "\n"
    if len(word) == 0:
        sleep(DELAY)
        toot(toot_now + "₍₍ ◝(* ,,Ծ‸Ծ,, )◟ ⁾⁾メッセージ入れてー！", g_vis ,id,None)
        return
    if len(word) > 300:
        sleep(DELAY)
        toot(toot_now + "₍₍ ◝(* ,,Ծ‸Ծ,, )◟ ⁾⁾長いよー！", g_vis ,id,None)
        return

    bm = bottlemail.Bottlemail()
    bm.bottling(acct,word,id)

    spoiler = "ボトルメール受け付けたよー！"
    toot_now += "受け付けたメッセージは「" + word + "」だよー！いつか届くから気長に待っててねー！"
    toot(toot_now, g_vis , id, spoiler)

#######################################################
# 受信したトゥートの一次振り分け処理
def th_worker():
    acct_list = []
    while True:
        try:
            status = TQ.get() #キューからトゥートを取り出すよー！なかったら待機してくれるはずー！
            #bot達のLTLトゥートは無視する(ง •̀ω•́)ง✧＜無限ループ防止！
            id = status["id"]
            acct = status["account"]["acct"]
            g_vis = status["visibility"]
            media_attachments = status["media_attachments"]
            sensitive = status['sensitive']
            if len(kiri_util.hashtag(status['content'])) > 0:
                continue
            content = kiri_util.content_cleanser(status['content'])
            spoiler_text = kiri_util.content_cleanser(status["spoiler_text"])
            if status['application'] == None:
                application = ''
            else:
                application = status['application']['name']

            enquete = None
            if status['enquete'] != None:
                enquete = json.loads(status['enquete'])

            a = int(CM.get_coolingtime())
            if  acct in BOTS:
                #ももながbotの場合もスルー
                if  acct == 'JC' and application != '女子会':
                    pass
                elif acct == '12222222' and 'ふきふき' in content:
                    pass
                else:
                    continue

            #連投防止
            # if  acct in acct_list and acct != MASTER_ID:
            #     continue

            if re.search(r"きりぼ.*(しりとり).*(しよ|やろ|おねがい|お願い)", content):
                fav_now(id)
                if StMG.is_game(acct):
                    toot('@%s 今やってる！\n※やめる場合は「しりとり終了」って言ってね'%acct, 'direct', id, None,interval=2)
                    continue

                StMG.add_game(acct)
                SM.update(acct, 'func')
                word1,yomi1,tail1 = StMG.games[acct].random_choice()
                result,text = StMG.games[acct].judge(word1)
                toot('@%s 【Lv.%d】じゃあ、%s【%s】の「%s」！\n※このトゥートにリプしてね！\n※DMでお願いねー！'%(acct,StMG.games[acct].lv,word1,yomi1,tail1) ,
                        'direct',  id, None,interval=2)

            elif StMG.is_game(acct) and re.search(r"(しりとり).*(終わ|おわ|終了|完了)", content) and g_vis == 'direct':
                fav_now(id)
                StMG.end_game(acct)
                toot('@%s おつかれさまー！\n(ラリー数：%d)'%(acct, StMG.games[acct].rcnt) , 'direct',  id, None,interval=2)

            elif StMG.is_game(acct) and g_vis == 'direct':
                fav_now(id)
                word = str(content).strip()
                result,text = StMG.games[acct].judge(word)
                if result:
                    if text == 'yes':
                        ret_word,ret_yomi,tail = StMG.games[acct].get_word(word)
                        if ret_word == None:
                            toot('@%s う〜ん！思いつかないよー！負けたー！\n(ラリー数：%d／%d点獲得)'%(acct,StMG.games[acct].rcnt,StMG.games[acct].rcnt*2+StMG.games[acct].lv), 'direct',  id, None,interval=2)
                            SM.update(acct, 'getnum', score=StMG.games[acct].rcnt*2+StMG.games[acct].lv)
                            StMG.end_game(acct)
                        else:
                            result2,text2 = StMG.games[acct].judge(ret_word)
                            if result2:
                                toot('@%s %s【%s】の「%s」！\n(ラリー数：%d)\n※このトゥートにリプしてね！\n※DMでお願いねー！'%(acct, ret_word, ret_yomi, tail, StMG.games[acct].rcnt), 'direct',  id, None,interval=2)
                            else:
                                toot('@%s %s【%s】\n%sえ〜ん負けたー！\n(ラリー数：%d／%d点獲得)'%(acct, ret_word, ret_yomi,text2, StMG.games[acct].rcnt,StMG.games[acct].rcnt+5+StMG.games[acct].lv), 'direct',  id, None,interval=2)
                                SM.update(acct, 'getnum', score=5+StMG.games[acct].rcnt+StMG.games[acct].lv)
                                StMG.end_game(acct)

                    else:
                        #辞書にない場合
                        toot('@%s %s\n※やめる場合は「しりとり終了」って言ってね！\n(ラリー数：%d)'%(acct,text, StMG.games[acct].rcnt), 'direct',  id, None,interval=2)
                else:
                    toot('@%s %s\nわーい勝ったー！\n(ラリー数：%d)'%(acct, text, StMG.games[acct].rcnt), 'direct',  id, None,interval=2)
                    StMG.end_game(acct)
            elif re.search(r"[!！]スロット", content) and g_vis == 'direct':
                fav_now(id)
                if re.search(r"100", content):
                    slot_rate = 100
                elif re.search(r"10", content):
                    slot_rate = 10
                else:
                    slot_rate = 1

                #所持金チェック
                acct_score = SM.show(acct)[0][1]
                if acct_score < slot_rate*3:
                    toot('@%s 得点足りないよー！（所持：%d点／必要：%d点）\nレートを下げるか他のゲームで稼いでねー！'%(acct,acct_score,slot_rate*3), 'direct', rep=id,interval=2)
                    continue
                #得点消費
                SM.update(acct, 'getnum', score=-slot_rate*3)
                #スロット回転
                slot_accts = DAO.get_five(num=5,minutes=120)
                slotgame = kiri_game.Friends_nico_slot(acct,slot_accts,slot_rate)
                slot_rows,slot_score = slotgame.start()
                sl_txt = ''
                for row in slot_rows:
                    for c in row:
                        sl_txt += c
                    sl_txt += '\n'
                if slot_score > 0:
                    SM.update(acct, 'getnum', score=slot_score)
                    acct_score = SM.show(acct)[0][1]
                    toot('@%s\n%s🎯当たり〜！！%d点獲得したよー！！（%d点消費／合計%d点）'%(acct, sl_txt, slot_score,slot_rate*3,acct_score), 'direct', rep=id, interval=5)
                else:
                    acct_score = SM.show(acct)[0][1]
                    toot('@%s\n%sハズレ〜〜（%d点消費／合計%d点）'%(acct, sl_txt ,slot_rate*3,acct_score), 'direct', rep=id, interval=5)

            elif re.search(r"(ヒントでピント)[：:]", content):
                if g_vis == 'direct':
                    word = re.search(r"(ヒントでピント)[：:](.+)", str(content)).group(2)
                    HintPintoQ.put([acct,id,word])
                    SM.update(acct, 'func')
                else:
                    toot('@%s ＤＭで依頼してねー！周りの人に答え見えちゃうよー！'%acct, 'direct', rep=id, interval=2)
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
                        toot(toot_now, g_vis, None, None,interval=5)

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
                    wikipedia.set_lang("ja")
                    page = wikipedia.page(word)
                except  wikipedia.exceptions.DisambiguationError as e:
                    toot('@%s 「%s」にはいくつか意味があるみたいだな〜'%(acct,word), g_vis, id, None, interval=1)
                except Exception as e:
                    print(e)
                    toot('@%s え？「%s」しらなーい！'%(acct,word), g_vis, id, None, interval=1)
                else:
                    summary_text = page.summary
                    if len(acct) + len(summary_text) + len(page.url) > 450:
                        summary_text = summary_text[0:450-len(acct)-len(page.url)] + '……'
                    toot('@%s %s\n%s'%(acct, summary_text, page.url), g_vis, id, 'なになに？「%s」とは……'%word, interval=1)

            elif len(media_attachments) > 0 and re.search(r"色[ぬ塗]って", content + spoiler_text):
                fav_now(id)
                for media in media_attachments:
                    filename = download(media["url"] , "media")
                    if '.mp' in filename or '.webm' in filename:
                        pass
                    else:
                        coloring_image(filename,acct,g_vis,id)
                        sleep(2)
            elif re.search(r"(私|わたし|わたくし|自分|僕|ぼく|俺|おれ|朕|ちん|余|あたし|ミー|あちき|あちし|あたい|\
                わい|わっち|おいどん|わし|うち|おら|儂|おいら|あだす|某|麿|拙者|小生|あっし|手前|吾輩|我輩|わらわ|ぅゅ)の(ランク|ランキング|順位|スコア|成績)", content):
                show_rank(acct=acct, target=acct, id=id, g_vis=g_vis)
                SM.update(acct, 'func')
            elif re.search(r":@(.+):.*の(ランク|ランキング|順位|スコア|成績)", content):
                word = re.search(r":@(.+):.*の(ランク|ランキング|順位|スコア|成績)", str(content)).group(1)
                show_rank(acct=acct, target=word, id=id, g_vis=g_vis)
                SM.update(acct, 'func')
            elif re.search(r"(数取りゲーム).*(おねがい|お願い)", content):
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
            elif len(content) > 40:
                if kiri_util.kiri_trans_detect(content) != 'ja':
                    fav_now(id)
                    toot_now = kiri_util.kiri_trans_xx2ja(kiri_util.kiri_trans_detect(content), content)
                    if re.search(r"[^:]@|^@", toot_now):
                        pass
                    else:
                        toot_now +=  "\n#きり翻訳 #きりぼっと"
                        toot(toot_now, 'public', id, '翻訳したよ〜！なになに……？ :@%s:＜'%acct ,interval=5)
                        SM.update(acct, 'func')
            elif  '翻訳して' in spoiler_text:
                fav_now(id)
                toot_now = kiri_util.kiri_trans_ja2en(content)
                if re.search(r"[^:]@|^@", toot_now):
                    pass
                else:
                    toot_now +=  "\n#きり翻訳 #きりぼっと"
                    toot(toot_now, 'public', id, '翻訳したよ〜！ :@%s:＜'%acct ,interval=5)
                    SM.update(acct, 'func')
            elif len(content) > 140 and (spoiler_text == None or spoiler_text == ''):
                content = re.sub(r"(.)\1{3,}",r"\1",content, flags=(re.DOTALL))
                gen_txt = Toot_summary.summarize(pat1.sub("",pat2.sub("",content)),limit=10,lmtpcs=1, m=1, f=4)
                if gen_txt[-1:1] == '#':
                    gen_txt = gen_txt[:len(gen_txt)-1]
                print('★要約結果：',gen_txt)
                if is_japanese(gen_txt):
                    if len(gen_txt) > 5:
                        gen_txt +=  "\n#きり要約 #きりぼっと"
                        toot("@" + acct + " :@" + acct + ":\n"  + gen_txt, g_vis, id, "勝手に要約サービス")
            elif re.search(r'[^:]@kiri_bot01', status['content']):
                if content.strip().isdigit():
                    continue
                if len(content) == 0:
                    continue
                fav_now(id)
                toot_now = "@%s\n"%acct
                toot_now += kiri_deep.lstm_gentxt("📣"+content,num=1)
                toot(toot_now, g_vis, id, None,interval=5)
            elif re.search(r"(きり|キリ).*(ぼっと|ボット|[bB][oO][tT])|[きキ][りリ][ぼボ]", content + spoiler_text):
                fav_now(id)
                if random.randint(0,10+a) > 9:
                    continue
                toot_now = "@%s\n"%acct
                toot_now += kiri_deep.lstm_gentxt("📣"+content,num=1)
                toot(toot_now, g_vis, id, None,interval=5)
                SM.update(acct, 'reply')
            else:
                if len(acct_list) > 0:
                    acct_list = acct_list[1:]
                continue

            #連投防止リスト更新
            acct_list.append(acct)
            if len(acct_list) > 2:
                acct_list = acct_list[1:]

            stm = CM.get_coolingtime()
            print('worker sleep :%fs'%stm )
            sleep(stm)
            # sleep(1)
        except Exception as e:
            print(e)
            kiri_util.error_log()


#######################################################
# 即時応答処理のスレッド
def th_quick():
    while True:
        try:
            status = QQ.get() #キューからトゥートを取り出すよー！なかったら待機してくれるはずー！
            quick_rtn(status)
        except Exception as e:
            print(e)
            kiri_util.error_log()

#######################################################
# 定期ものまねさーびす！
def monomane_tooter():
    spoiler = "勝手にものまねサービス"
    random_acct = DAO.sample_acct()
    toots = ""
    for row in DAO.get_user_toots(random_acct):
        if len(kiri_util.hashtag(row[0])) > 0:
            continue
        content = kiri_util.content_cleanser(row[0])
        if len(content) == 0:
            continue
        toots += content + "。\n"
    chain = PrepareChain.PrepareChain("user_toots",toots)
    triplet_freqs = chain.make_triplet_freqs()
    chain.save(triplet_freqs, True)
    generator = GenerateText.GenerateText(5)
    gen_txt = generator.generate("user_toots")
    gen_txt = "@" + random_acct + " :@" + random_acct + ":＜「" + gen_txt + "」"
    gen_txt = gen_txt.replace('\n',"")
    #gen_txt +=  "\n#きりものまね #きりぼっと"
    SM.update(random_acct, 'func')
    if len(gen_txt) > 10:
        toot(gen_txt, "unlisted", None, spoiler)

#######################################################
# ○○○○
def tangrkn_tooter():
    spoiler = "○○モノマネ"
    generator = GenerateText.GenerateText(5)
    gen_txt = generator.generate("tangrkn")
    if len(gen_txt) > 10:
        toot(gen_txt, "private", spo=spoiler)

#######################################################
# 陣形
def jinkei_tooter():
    spoiler = "勝手に陣形サービス"
    gen_txt = kiri_romasaga.gen_jinkei()
    # gen_txt = '@kiritan\n' + gen_txt
    toot(gen_txt, "public", spo=spoiler)

#######################################################
# 定期ここ1時間のまとめ
# def summarize_tooter():
#     spoiler = "ＬＴＬここ1時間の自動まとめ"
#     toots = ""
#     for row in DAO.get_toots_1hour():
#         if len(kiri_util.hashtag(row[0])) > 0:
#             continue
#         content = kiri_util.content_cleanser(row[0])
#         if len(content) == 0:
#             continue
#         content = re.sub(r"(.+)\1{3,}","",content, flags=(re.DOTALL))
#         toots += content + "\n"
#     gen_txt = Toot_summary.summarize(pat1.sub("",pat2.sub("",toots)),limit=90, lmtpcs=5, m=1, f=4)
#     if gen_txt[-1:1] == '#':
#         gen_txt = gen_txt[:len(gen_txt)-1]
#     if len(gen_txt) > 5:
#         toot(gen_txt, "unlisted", None, spoiler)
#
#######################################################
# ボトルメールサービス　配信処理
def bottlemail_sending():
    bm = bottlemail.Bottlemail()
    sendlist = bm.drifting()
    for id,acct,msg,reply_id in sendlist:
        sleep(DELAY)
        spoiler = ":@" + acct + ": から🍾ボトルメール💌届いたよー！"
        random_acct = DAO.sample_acct()
        #お届け！
        toots = "@" + random_acct + "\n:@" + acct + ":＜「" + msg + "」"
        toots +=  "\n※ボトルメールサービス：＜メッセージ＞　であなたも送れるよー！試してみてね！"
        toots +=  "\n#ボトルメールサービス #きりぼっと"
        toot(toots, "direct",reply_id if reply_id != 0 else None, spoiler)
        bm.sended(id, random_acct)

        #到着通知
        sleep(DELAY)
        spoiler = ":@" + random_acct + ": が🍾ボトルメール💌受け取ったよー！"
        toots = "@" + acct + " 届けたメッセージは……\n:@" + acct + ": ＜「" + msg + "」"
        toots +=  "\n#ボトルメールサービス #きりぼっと"
        toot(toots, "direct",reply_id if reply_id != 0 else None, spoiler)

    #漂流してるボトルの数
    #ボトルが多い時は宣伝を減らすよー！
    # bmcnt = bm.flow_count()
    # if random.randint(0,bmcnt) <= 10:
    #     sleep(DELAY)
    #     spoiler = "現在漂流している🍾ボトルメール💌は%d本だよー！"%bmcnt
    #     toots =  "\n※ボトルメールサービス：＜メッセージ＞　であなたも送れるよー！試してみてね！"
    #     toots +=  "\n#ボトルメールサービス #きりぼっと"
    #     toot(toots, "public", None, spoiler)

#######################################################
# 初めてのトゥートを探してぶーすとするよー！
def timer_bst1st():
    random_acct = DAO.sample_acct()
    boost_now(DAO.get_random_1id(random_acct))
    SM.update(random_acct, 'func')

#######################################################
# きりぼっとのつぶやき
def lstm_tooter():
    # kiri_deep.reload_model()
    seeds = DAO.get_least_10toots()
    #print('seeds',seeds)
    if len(seeds) <= 2:
        return
    seedtxt = "📣" + "\n📣".join(seeds)
    spoiler = None

    gen_txt = kiri_deep.lstm_gentxt(seedtxt,num=1)
    if gen_txt[0:1] == '。':
        gen_txt = gen_txt[1:]
    if len(gen_txt) > 40:
        spoiler = ':@%s: 💭'%BOT_ID

    toot(gen_txt, "public", None, spoiler)

#######################################################
# DELETE時の処理
def th_delete():
    acct_1b = ''
    while True:
        try:
            toot_now = '@%s \n'%MASTER_ID
            row = DAO.pickup_1toot(DelQ.get())
            print('th_delete:',row)
            if row:
                if acct_1b != row[0]:
                    date = '{0:08d}'.format(row[2])
                    time = '{0:06d}'.format(row[3])
                    ymdhms = '%s %s'%(date,time)
                    ymdhms = dateutil.parser.parse(ymdhms).astimezone(timezone('Asia/Tokyo'))
                    toot_now += ':@%s: 🚓🚓🚓＜う〜う〜！トゥー消し警察でーす！\n'%row[0]
                    toot_now += ':@%s: ＜「%s」 at %s'%(row[0], kiri_util.content_cleanser(row[1]) , ymdhms.strftime("%Y.%m.%d %H:%M:%S"))
                    toot(toot_now, 'direct', rep=None, spo=':@%s: がトゥー消ししたよー……'%row[0], media_ids=None, interval=0)
                    acct_1b = row[0]
                    SM.update(row[0], 'func', score=-1)
        except Exception as e:
            print(e)
            kiri_util.error_log()


#######################################################
# ヒントでピントゲーム
def th_hint_de_pinto():
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
        for i in range(y,1,- int(y*3/10)):
            if len(break_flg) == 0:
                tmp = img.resize((int(img.width/i), int(img.height/i)),Image.NEAREST)  #LANCZOS BICUBIC NEAREST
                tmp = tmp.resize((img.width, img.height),Image.NEAREST)
                filename = path.split('.')[0] + '_{0}.png'.format(y)
                tmp.save(filename,ex, optimize=True)
                media_files = []
                media_files.append(mastodon.media_post(filename, 'image/' + ex))
                toot_now = "さて、これは何/誰でしょうか？\nヒント：{0}\n#きりたんのヒントでピント".format(hint_text)
                toot(toot_now, g_vis='private', rep=None, spo=None, media_ids=media_files)
                for tt in range(60):
                    sleep(1)
                    if len(break_flg) > 0:
                        break
                # sleep(60)
                # sleep(5)
            else:
                break

            loop += 1
            loop_cnt.append(loop)
            if loop == 1:
                hint_text = "○"*len(term)
            elif len(term) > loop - 1:
                hint_text = term[0:loop-1] + "○"*(len(term) - (loop-1))



        sleep(5)
        media_files = []
        media_files.append(mastodon.media_post(path, 'image/' + ex))
        toot_now = "正解は{0}でした〜！\n（出題 :@{1}: ）".format(term,acct)
        toot(toot_now, g_vis='private', rep=None, spo=None, media_ids=media_files)

    gi = kiri_util.get_images(BING_KEY)
    junbiTM = kiri_util.KiriTimer(1200)
    junbiTM.reset(0)
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
            print('ans=',ans)
            if not th.is_alive():
                break
            if g_acct != acct and term in ans:
                loop = len(loop_cnt)
                score = 96//(2**loop)
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
def th_gettingnum():
    gamenum = 100
    junbiTM = kiri_util.KiriTimer(60*60)
    junbiTM.reset(50*60)
    junbiTM.start()
    gameTM = kiri_util.KiriTimer(240)
    while True:
        try:
            g_acct,g_id = GetNumQ.get()
            if junbiTM.check() > 0:
                sleep(3)
                remaintm = junbiTM.check()
                toot('@%s\n開催準備中だよー！あと%d分%d秒待ってねー！'%(g_acct,remaintm//60,remaintm%60), 'unlisted', g_id, None)
                sleep(27)
                continue

            #アクティブ人数確認
            i = DAO.get_gamenum()
            if  i <= 10:
                sleep(3)
                toot('@%s\n人少ないからまた後でねー！'%g_acct, 'unlisted', g_id, None)
                sleep(27)
                continue

            #ゲーム開始ー！
            fav_now(g_id)
            sleep(DELAY)
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
            if len(results) <= 0:
                toot('(ง •̀ω•́)ง✧数取りゲーム、０人だったよー！\n#数取りゲーム #きりぼっと', 'public', None, None)
            else:
                toot_now = ''
                hanamaru = False
                for val,accts in sorted(results.items(), key=lambda x: -x[0]):
                    if len(accts) == 0:
                        continue
                    elif len(accts) == 1 and not hanamaru:
                        toot_now += '💮'
                        hanamaru = True
                        print('#######%sに%d点！'%(accts[0],val))
                        SM.update(accts[0], 'getnum', score=val)
                    else:
                        toot_now += '❌'

                    toot_now += '{0:>2}：'.format(val)
                    for acct1 in accts:
                        toot_now += ':@%s:'%acct1
                    toot_now += '\n'
                toot('%s\n#数取りゲーム #きりぼっと'%toot_now, 'public', None, '数取りゲーム、結果発表ーー！！')

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
                DAO.save_toot(status)
            except Exception as e:
                #保存失敗したら、キューに詰めてリトライ！
                #StatusQ.put(status)
                print(e)
                kiri_util.error_log()
    except Exception as e:
        print(e)
        kiri_util.error_log()
        # sleep(30)
        # th_saver()

#######################################################
# ローカルタイムライン監視スレッド
def t_local():
    try:
        # mastodon.stream_public(ltl_listener())
        mastodon.stream_local(ltl_listener())
    except Exception as e:
        print(e)
        kiri_util.error_log()
        # sleep(30)
        # t_local()

#######################################################
# ローカルタイムライン監視スレッド（認証なし）
def t_sub():
    try:
        publicdon.stream_local(public_listener())
    except Exception as e:
        print(e)
        kiri_util.error_log()
        # sleep(30)
        # t_sub()

#######################################################
# ホームタイムライン監視スレッド
def t_user():
    try:
        mastodon.stream_user(notification_listener())
    except Exception as e:
        print(e)
        kiri_util.error_log()
        # sleep(30)
        # t_user()

#######################################################
# randomニコルくん
def th_nicoru():
    gen_txt = ''
    while len(gen_txt) < 430:
        gen_txt += ':nicoru{0}:'.format(random.randint(0,360))
    toot('@%s '%MASTER_ID + gen_txt, "direct", None, None)

#######################################################
# フォロ外し
def th_follow_mente():
    print('🌠フォローフォロワー整理処理ーー！！')
    ret = mastodon.account_verify_credentials()
    uid = ret['id']
    sleep(1)
    ret = mastodon.account_following(uid, max_id=None, since_id=None, limit=80)
    fids = []
    while '_pagination_next' in ret[-1].keys():
        for account in ret:
            fids.append(account['id'])
        max_id = ret[-1]['_pagination_next']['max_id']
        sleep(1)
        ret = mastodon.account_following(uid, max_id=max_id, since_id=None, limit=80)
    for account in ret:
        fids.append(account['id'])
    print('　　フォロー：',len(fids))
    sleep(1)
    ret = mastodon.account_followers(uid, max_id=None, since_id=None, limit=80)
    fers = []
    while '_pagination_next' in ret[-1].keys():
        for account in ret:
            fers.append(account['id'])
        max_id = ret[-1]['_pagination_next']['max_id']
        sleep(1)
        ret = mastodon.account_followers(uid, max_id=max_id, since_id=None, limit=80)
    for account in ret:
        fers.append(account['id'])
    print('　　フォロワー：',len(fers))
    sleep(1)
    for u in set(fers) - set(fids):
        try:
            mastodon.account_follow(u)
        except Exception as e:
            print(e)
            kiri_util.error_log()
        sleep(1)
    for u in set(fids) - set(fers):
        try:
            mastodon.account_unfollow(u)
        except Exception as e:
            print(e)
        sleep(1)

#######################################################
# post用worker
def th_post():
    try:
        while True:
            func,args = PostQ.get()
            sleep(1)
            func(*args)
            sleep(2)
    except Exception as e:
        print(e)
        kiri_util.error_log()

#######################################################
# メイン
def main():
    threads = []
    #タイムライン受信系
    threads.append( threading.Thread(target=t_local ) ) #LTL
    threads.append( threading.Thread(target=t_user ) ) #LTL
    threads.append( threading.Thread(target=t_sub ) ) #LTL
    #タイムライン応答系
    threads.append( threading.Thread(target=th_worker) )
    threads.append( threading.Thread(target=th_delete) )
    threads.append( threading.Thread(target=th_saver) )
    threads.append( threading.Thread(target=th_gettingnum) )
    threads.append( threading.Thread(target=th_hint_de_pinto) )
    threads.append( threading.Thread(target=th_quick) )
    threads.append( threading.Thread(target=th_post) )
    #スケジュール起動系
    # threads.append( threading.Thread(target=kiri_util.scheduler, args=(summarize_tooter,['02'])) )
    threads.append( threading.Thread(target=kiri_util.scheduler, args=(bottlemail_sending,['05'])) )
    # threads.append( threading.Thread(target=kiri_util.scheduler, args=(monomane_tooter,None,120,0,15,CM)) )
    threads.append( threading.Thread(target=kiri_util.scheduler, args=(lstm_tooter,None,5,-3,2,CM)) )
    # threads.append( threading.Thread(target=kiri_util.scheduler, args=(timer_bst1st,None,90,0,15,CM)) )
    #threads.append( threading.Thread(target=kiri_util.scheduler, args=(th_nicoru,None,60,0,60,CM)) )
    threads.append( threading.Thread(target=kiri_util.scheduler, args=(th_follow_mente,None,60*24)) )
    # threads.append( threading.Thread(target=kiri_util.scheduler, args=(tangrkn_tooter,None,20,-10,10,CM)) )
    threads.append( threading.Thread(target=kiri_util.scheduler, args=(jinkei_tooter,None,120,-10,10,CM)) )

    for th in threads:
        th.start()
    for th in threads:
        th.join()

if __name__ == '__main__':
    main()
