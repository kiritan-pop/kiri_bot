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
import kiri_util, kiri_deep, kiri_game

MASTER_ID = 'kiritan'
BOT_ID = 'kiri_bot01'
BOTS = [BOT_ID,'friends_booster','5']
DELAY = 2
pat1 = re.compile(r' ([!-~ぁ-んァ-ン] )+|^([!-~ぁ-んァ-ン] )+| [!-~ぁ-んァ-ン]$',flags=re.MULTILINE)  #[!-~0-9a-zA-Zぁ-んァ-ン０-９ａ-ｚ]
pat2 = re.compile(r'[ｗ！？!\?]')

#得点管理、流速監視
SM = kiri_util.ScoreManager()
CM = kiri_util.CoolingManager(10)
DAO = kiri_util.DAO_statuses()

#.envファイルからトークンとかURLを取得ー！
dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)
MASTODON_URL = os.environ.get("MASTODON_URL")
MASTODON_ACCESS_TOKEN = os.environ.get("MASTODON_ACCESS_TOKEN")


publicdon = Mastodon(api_base_url=MASTODON_URL)  # インスタンス

mastodon = Mastodon(
    access_token=MASTODON_ACCESS_TOKEN,
    api_base_url=MASTODON_URL)  # インスタンス

TQ = queue.Queue()
QQ = queue.Queue()
StatusQ = queue.Queue()
Toot1bQ = queue.Queue()
DelQ = queue.Queue()
GetNumQ = queue.Queue()
GetNumVoteQ = queue.Queue()
GetNum_flg = []

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
class men_toot(StreamListener):
    def on_notification(self, notification):
        print("===通知===")
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        ymdhms = jst_now.strftime("%Y%m%d %H%M%S")

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

#######################################################
# マストドンＡＰＩ用部品を継承して、ローカルタイムライン受信時の処理を実装ー！
class res_toot(StreamListener):
    def on_update(self, status):
        #print("===パブリックタイムライン===")
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

#######################################################
# タイムライン保存用（認証なし）
class public_listener(StreamListener):
    def on_update(self, status):
            QQ.put(status)
            StatusQ.put(status)
            CM.count(status['created_at'])

    def on_delete(self, status_id):
        print(str("===削除されました【{}】===").format(str(status_id)))
        DelQ.put(status_id)

#######################################################
# トゥート処理
def toot(toot_now, g_vis='direct', rep=None, spo=None, media_ids=None, interval=0):
    def th_toot(toot_now, g_vis, rep, spo, media_ids):
        if rep != None:
            try:
                status = mastodon.status(rep)
            except Exception:
                mastodon.status_post(status=toot_now[0:450], visibility=g_vis, in_reply_to_id=None, spoiler_text=spo, media_ids=media_ids)
            else:
                mastodon.status_post(status=toot_now[0:450], visibility=g_vis, in_reply_to_id=rep, spoiler_text=spo, media_ids=media_ids)
        else:
            mastodon.status_post(status=toot_now[0:450], visibility=g_vis, in_reply_to_id=None, spoiler_text=spo, media_ids=media_ids)

    th = threading.Timer(interval=interval,function=th_toot,args=(toot_now, g_vis, rep, spo, media_ids))
    th.start()
    print("🆕toot:" + toot_now[0:50] + ":" + g_vis )

#######################################################
# ファボ処理
def fav_now(id):  # ニコります
    try:
        status = mastodon.status(id)
    except:
        pass
    else:
        if status['favourited'] == False:
            #mastodon.status_favourite(id)
            th = threading.Timer(interval=2,function=mastodon.status_favourite,args=(id,))
            th.start()
            print("🙆Fav")

#######################################################
# ブースト
def boost_now(id):  # ぶーすと！
    try:
        status = mastodon.status(id)
    except:
        pass
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
    status = mastodon.status(id)
    if status['reblogged'] == True:
        mastodon.status_unreblog(id)
        print("🙆unboost")

#######################################################
# フォロー
def follow(id):
    th = threading.Timer(interval=8,function=mastodon.account_follow,args=(id,))
    th.start()
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
                toot('@%s\n₍₍ ◝(◍•ᴗ•◍)◟⁾⁾また後でねー！'%acct, 'direct', id, None)
        else:
            if len(GetNum_flg) > 0:
                if content.strip().isdigit():
                    GetNumVoteQ.put([acct,id,int(content.strip())])
            else:
                if content.strip().isdigit():
                    toot('@%s\n₍₍ ◝(◍•ᴗ•◍)◟⁾⁾また後でねー！'%acct, 'direct', id, None)

#######################################################
# 画像判定
def ana_image(media_attachments,sensitive,acct):
    toot_now = ''
    for media in media_attachments:
        filename = download(media["url"] , "media")
        if '.mp' in filename or '.webm' in filename:
            continue
        result = kiri_deep.takoramen(filename)
        print('   ',result)
        if result == 'other':
            continue
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
            toot_now += '色塗ってー！'
        elif result == 'ろびすて':
            toot_now += '🙏ろびすてとうとい！'
        elif result == '漫画':
            toot_now += 'それなんて漫画ー？'
        elif result in  ['スクショ','汚部屋','部屋','自撮り','太もも']:
            toot_now += result + 'だー！'
        elif result == 'kent':
            toot_now += 'ケント丸だー！'
        elif sensitive:
            if 'ラーメン' in result or '麺' in result or result == 'うどｎ' or  result == 'そば' or result == 'パスタ':
                toot_now += '🍜%sちゅるちゅるーっ！'%result
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
            else:
                toot_now += result + 'だー！おいしそうー！'
        else:
            toot_now += ':@%s: 🚓🚓🚓＜う〜う〜！飯テロ警察 %s係でーす！\n'%(acct,result)
            break

    return toot_now

#######################################################
# 即時応答処理ー！
def quick_rtn(status):
    id = status["id"]
    acct = status["account"]["acct"]
    username = "@" +  acct
    g_vis = status["visibility"]
    if len(kiri_util.hashtag(status['content'])) > 0:
        return
    content = kiri_util.content_cleanser(status['content'])
    if status['application'] == None:
        application = ''
    else:
        application = status['application']['name']
    print('===%s\t「%s」'%(acct, '\n    '.join(content.split('\n'))))
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
        return
    #ももながbotの場合もスルー
    if  acct == 'JC' and application == '女子会':
        return
    if  acct == 'neruru' and application == 'Futomomodaisuki':
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
    rnd = random.randint(0,8+a*2)
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
                if rnd <= 6:
                    #toot_now = '　　三(  っ˃̵ᴗ˂̵) 通りまーす！'
                    toot_now = ':nicoru180: :nicoru180: :nicoru180: :nicoru180: :nicoru180: '
                    id_now = None
    elif re.search(r"(:nicoru[0-9]{0,3}:.?){2}", content):
        if content_1b != None and acct == acct_1b:
            SM.update(acct, 'func')
            if re.search(r"(:nicoru[0-9]{0,3}:.?){3}", content_1b):
                SM.update(acct, 'func')
                if rnd <= 6:
                    #toot_now = '　　(˃̵ᴗ˂̵っ )三 通りまーす！'
                    toot_now = ':nicoru180:'
                    id_now = None
    elif re.search(r"^貞$", content):
        if content_1b != None and acct == acct_1b:
            SM.update(acct, 'func',score=-1)
            if re.search(r"^治$", content_1b):
                SM.update(acct, 'func')
                if rnd <= 7:
                    toot_now = '　　三(  っ˃̵ᴗ˂̵) 通りまーす！'
                    id_now = None

    if acct == acct_1b:
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
    elif re.search(r"草", content+spoiler_text):
        SM.update(acct, 'func',score=-1)
        if rnd <= 1:
            toot_now = ":" + username + ": "
            random.shuffle(hanalist)
            toot_now += hanalist[0] + ' 三💨 ﾋﾟｭﾝ!!'
            id_now = None
    elif re.search(r"^:twitter:.+🔥$", content, flags=(re.MULTILINE | re.DOTALL)):
        SM.update(acct, 'func')
        if rnd <= 2:
            toot_now = ':twitter: ＜ﾊﾟﾀﾊﾟﾀｰ\n川\n\n🔥'
            id_now = None
        elif rnd == 6:
            toot_now = '(ﾉ・_・)ﾉ ﾆｹﾞﾃ!⌒:twitter: ＜ｱﾘｶﾞﾄｩ!\n🔥'
            id_now = None
        elif rnd == 7:
            toot_now = '(ﾉ・_・)ﾉ ﾆｹﾞﾃ!⌒🍗 ＜ｱﾘｶﾞﾄｩ!\n🔥'
            id_now = None
    elif re.search(r"ブリブリ|ぶりぶり|うん[ちこ]|💩|^流して$", content+spoiler_text):
        SM.update(acct, 'func',score=-1)
        if rnd <= 2:
            toot_now = '🌊🌊🌊🌊 ＜ざばーっ！'
            id_now = None
    elif re.search(r"^ふきふき$|^竜巻$", content):
        SM.update(acct, 'func')
        if rnd <= 1:
            toot_now = '🌪🌪🌪🌪＜ごぉ〜〜っ！'
            id_now = None
        elif rnd <= 2:
            toot_now = '💨💨💨🍃＜ぴゅ〜〜っ！'
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
    elif re.search(r"^ぬるぽ$", content):
        SM.update(acct, 'func',score=-1)
        if rnd <= 4:
            toot_now = 'ｷﾘｯ'
            id_now = None
    elif re.search(r"^通過$", content):
        toot_now = '%s ( ⊂๑˃̵᎑˂̵)⊃＜阻止！'%username
        vis_now = 'direct'
        SM.update(acct, 'func')
        if rnd <= 4:
            toot_now = '⊂(˃̵᎑˂̵๑⊃ )＜阻止！'
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
        if rnd <= 2:
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
        if rnd <= 1:
            toot_now = '٩(`^´๑ )۶三٩(๑`^´๑)۶三٩( ๑`^´)۶'
            id_now = None
        if rnd == 2:
            toot_now = '٩(`^´๑ )۶三٩( ๑`^´)۶'
            id_now = None
        if rnd == 3:
            toot_now = ' ₍₍ ٩(๑`^´๑)۶ ⁾⁾おぢおぢダンスーー♪'
            id_now = None
    elif len(media_attachments) > 0:
        toot_now = ana_image(media_attachments,sensitive,acct)
        id_now = None
        # interval = 3
    elif acct == MASTER_ID:
        fav_now(id_now)
    else:
        return
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
    if ymdhms == None:
        toot_now = '@%s 新規さんかも−！\n:@%s:(%s)＜「%s」(created at %s)'%(MASTER_ID, acct, display_name, content, ac_ymd)
        toot(toot_now)
    elif ymdhms + diff < created_at:
        toot_now = '@%s 帰ってきたよ−！(前回書込：%s)\n:@%s:(%s)＜「%s」'%(MASTER_ID, ymdhms.strftime("%Y.%m.%d %H:%M:%S"), acct, display_name, content)
        #toot(toot_now)

    watch_list = set([kansi_acct.strip() for kansi_acct in open('.watch_list').readlines()])
    if acct in watch_list:
        toot_now = '@%s :@%s: %s\n「%s」'%(MASTER_ID, acct, display_name, content)
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
def show_rank(acct, id, g_vis):
    if not os.path.exists("db/statuses_today.json") :
        return

    fav_now(id)
    dt = datetime.fromtimestamp(os.stat("db/statuses_today.json").st_mtime)
    today_str = dt.strftime('%Y/%m/%d')
    users_cnt = {}
    with open("db/users_cnt.json", 'r') as f:
        users_cnt = json.load(f)
    users_size = {}
    with open("db/users_size.json", 'r') as f:
        users_size = json.load(f)
    faboo_cnt = {}
    with open("db/faboo_cnt.json", 'r') as f:
        faboo_cnt = json.load(f)

    users_ranking = {}
    for i,(k_acct, cnt) in enumerate(sorted(users_cnt.items(), key=lambda x: -x[1])):
        users_ranking[k_acct] = [i+1, cnt, users_size[k_acct]]
        #print(users_ranking[k_acct])

    if acct not in users_cnt:
        toot('@%s …ランク外だよー！どんまい！'%acct, g_vis ,id, None)
        return

    toot_now = "@{0}\n:@{1}: のランクだよー！\n（※{2} 時点）\n".format(acct,acct,today_str)
    toot_now += "{0:>3}位 {1:>4} toots/ニコブ率{2:.1f}％".format(users_ranking[acct][0], users_ranking[acct][1],
                                                               faboo_cnt[acct]*100/users_ranking[acct][1])
    toot(toot_now, g_vis ,id)

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
    while True:
        try:
            status = TQ.get() #キューからトゥートを取り出すよー！なかったら待機してくれるはずー！
            #bot達のLTLトゥートは無視する(ง •̀ω•́)ง✧＜無限ループ防止！
            id = status["id"]
            acct = status["account"]["acct"]
            g_vis = status["visibility"]
            if len(kiri_util.hashtag(status['content'])) > 0:
                continue
            content = kiri_util.content_cleanser(status['content'])
            spoiler_text = kiri_util.content_cleanser(status["spoiler_text"])
            if status['application'] == None:
                application = ''
            else:
                application = status['application']['name']
            a = int(CM.get_coolingtime())
            if  acct in BOTS:
                continue
            #ももながbotの場合もスルー
            if  acct == 'JC' and application == '女子会':
                continue
            if  acct == 'neruru' and application == 'Futomomodaisuki':
                continue
            if re.search(r"(連想|れんそう)([サさ]ー[ビび][スす])[：:]", content):
                toot('@%s このサービスは終了したよ〜(৹ᵒ̴̶̷᷄﹏ᵒ̴̶̷᷅৹)'%acct, g_vis, id, None,interval=3)
                #rensou_game(content=content, acct=acct, id=id, g_vis=g_vis)
                #SM.update(acct, 'func')
            elif re.search(r"(画像検索)([サさ]ー[ビび][スす])[：:]", content):
                toot('@%s このサービスは終了したよ〜(৹ᵒ̴̶̷᷄﹏ᵒ̴̶̷᷅৹)'%acct, g_vis, id, None,interval=3)
                #search_image(content=content, acct=acct, id=id, g_vis=g_vis)
                #SM.update(acct, 'func')
            elif re.search(r"(スパウザー)([サさ]ー[ビび][スす])[：:]", content):
                toot('@%s このサービスは終了したよ〜(৹ᵒ̴̶̷᷄﹏ᵒ̴̶̷᷅৹)'%acct, g_vis, id, None,interval=3)
                #supauza(content=content, acct=acct, id=id, g_vis=g_vis)
                #SM.update(acct, 'func')
            elif re.search(r"([ぼボ][とト][るル][メめ]ー[るル])([サさ]ー[ビび][スす])[：:]", content):
                print("★ボトルメールサービス")
                bottlemail_service(content=content, acct=acct, id=id, g_vis=g_vis)
                SM.update(acct, 'func')
            elif re.search(r"(きょう|今日)の.?(料理|りょうり)", content):
                recipe_service(content=content, acct=acct, id=id, g_vis=g_vis)
                SM.update(acct, 'func')
            elif re.search(r"\s?(.+)って(何|なに|ナニ)\?$", content):
                word = re.search(r"\s?(.+)って(何|なに|ナニ)\?$", str(content)).group(1)
                SM.update(acct, 'func')
                try:
                    wikipedia.set_lang("ja")
                    page = wikipedia.page(word)
                except  wikipedia.exceptions.DisambiguationError as e:
                    toot('@%s 「%s」にはいくつか意味があるみたいだな〜'%(acct,word), g_vis, id, None, interval=1)
                except Exception:
                    toot('@%s え？「%s」しらなーい！'%(acct,word), g_vis, id, None, interval=1)
                else:
                    summary_text = page.summary
                    if len(acct) + len(summary_text) + len(page.url) > 450:
                        summary_text = summary_text[0:450-len(acct)-len(page.url)] + '……'
                    toot('@%s %s\n%s'%(acct, summary_text, page.url), g_vis, id, 'なになに？「%s」とは……'%word, interval=1)

            elif re.search(r"(私|わたし|わたくし|自分|僕|俺|朕|ちん|余|あたし|ミー|あちき|あちし|\
                わい|わっち|おいどん|わし|うち|おら|儂|おいら|あだす|某|麿|拙者|小生|あっし|手前|吾輩|我輩|マイ)の(ランク|ランキング|順位)", content):
                #toot('@%s このサービスは終了したよ〜(৹ᵒ̴̶̷᷄﹏ᵒ̴̶̷᷅৹)'%acct, g_vis, id, None,interval=3)
                show_rank(acct=acct, id=id, g_vis=g_vis)
                SM.update(acct, 'func')
            elif re.search(r"(数取りゲーム).*(おねがい|お願い)", content):
                print('数取りゲーム受信')
                GetNumQ.put([acct,id])
                SM.update(acct, 'func')
            elif  '?トゥトゥトゥ' in content and acct == 'twotwo': #ネイティオ専用
                GetNumQ.put([acct,id])
                SM.update(acct, 'func')
            elif len(content) > 140 and spoiler_text == None:
                content = re.sub(r"(.)\1{3,}",r"\1",content, flags=(re.DOTALL))
                gen_txt = Toot_summary.summarize(pat1.sub("",pat2.sub("",content)),limit=10,lmtpcs=1, m=1, f=4)
                if gen_txt[-1:1] == '#':
                    gen_txt = gen_txt[:len(gen_txt)-1]
                print('★要約結果：',gen_txt)
                if is_japanese(gen_txt):
                    if len(gen_txt) > 5:
                        gen_txt +=  "\n#きり要約 #きりぼっと"
                        toot("@" + acct + " :@" + acct + ":\n"  + gen_txt, g_vis, id, "勝手に要約サービス")
            elif re.search(r"(きり|キリ).*(ぼっと|ボット|[bB][oO][tT])|[きキ][りリ][ぼボ]", content + spoiler_text):
                fav_now(id)
                if random.randint(0,10+a) > 3:
                    continue
                toot_now = "@%s\n"%acct
                toot_now += kiri_deep.lstm_gentxt(content,num=1)
                toot(toot_now, g_vis, id, None,interval=5)
                SM.update(acct, 'reply')
            elif re.search(r'[^:]@kiri_bot01', status['content']):
                if content.strip().isdigit():
                    continue
                if len(content) == 0:
                    continue
                fav_now(id)
                toot_now = "@%s\n"%acct
                toot_now += kiri_deep.lstm_gentxt(content,num=1)
                toot(toot_now, g_vis, id, None,interval=5)
            elif re.search(r"めいめい|めーめー", content + spoiler_text):
                if random.randint(0,10+a) > 3:
                    continue
                fav_now(id)
                toot_now = "@%s\n:@mei23:＜「"%acct
                toot_now += kiri_deep.lstm_gentxt(content,num=1,sel_model='mei23').strip() + '」'
                toot(toot_now, g_vis, id, None,interval=5)
                SM.update(acct, 'func')
            elif re.search(r"きりたん|きりきり|きりっち", content + spoiler_text):
                if random.randint(0,10+a) > 3:
                    continue
                fav_now(id)
                toot_now = "@%s\n:@kiritan:＜「"%acct
                toot_now += kiri_deep.lstm_gentxt(content,num=1,sel_model='kiritan').strip() + '」'
                toot(toot_now, g_vis, id, None,interval=5)
                SM.update(acct, 'func')
            elif re.search(r"神埼|お兄さん|おにいさん|なか[卯う]|100db|ダンボッチ|騒音", content + spoiler_text):
                if random.randint(0,10+a) > 3:
                    continue
                fav_now(id)
                toot_now = "@%s\n:@Knzk:＜「"%acct
                toot_now += kiri_deep.lstm_gentxt(content,num=1,sel_model='knzk').strip() + '😋😋😋」'
                toot(toot_now, g_vis, id, None,interval=5)
                SM.update(acct, 'func')
            elif re.search(r"チノ|ラマーズ", content + spoiler_text):
                if random.randint(0,10+a) > 3:
                    continue
                fav_now(id)
                toot_now = "@%s\n:@lamazeP:＜「"%acct
                toot_now += kiri_deep.lstm_gentxt(content,num=1,sel_model='chino').strip() + '」'
                toot(toot_now, g_vis, id, None,interval=5)
                SM.update(acct, 'func')
            else:
                continue

            stm = CM.get_coolingtime()
            print('worker sleep :%fs'%stm )
            sleep(stm)
        except Exception:
            kiri_util.error_log()

#######################################################
# 即時応答処理のスレッド
def th_quick():
    while True:
        try:
            status = QQ.get() #キューからトゥートを取り出すよー！なかったら待機してくれるはずー！
            quick_rtn(status)
        except Exception:
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
# 定期ここ1時間のまとめ
def summarize_tooter():
    spoiler = "ＬＴＬここ1時間の自動まとめ"
    toots = ""
    for row in DAO.get_toots_1hour():
        if len(kiri_util.hashtag(row[0])) > 0:
            continue
        content = kiri_util.content_cleanser(row[0])
        if len(content) == 0:
            continue
        content = re.sub(r"(.+)\1{3,}","",content, flags=(re.DOTALL))
        toots += content + "\n"
    gen_txt = Toot_summary.summarize(pat1.sub("",pat2.sub("",toots)),limit=90, lmtpcs=5, m=1, f=4)
    if gen_txt[-1:1] == '#':
        gen_txt = gen_txt[:len(gen_txt)-1]
    if len(gen_txt) > 5:
        toot(gen_txt, "unlisted", None, spoiler)

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
    bmcnt = bm.flow_count()
    if random.randint(0,bmcnt) <= 10:
        sleep(DELAY)
        spoiler = "現在漂流している🍾ボトルメール💌は%d本だよー！"%bmcnt
        toots =  "\n※ボトルメールサービス：＜メッセージ＞　であなたも送れるよー！試してみてね！"
        toots +=  "\n#ボトルメールサービス #きりぼっと"
        toot(toots, "public", None, spoiler)

#######################################################
# 初めてのトゥートを探してぶーすとするよー！
def timer_bst1st():
    random_acct = DAO.sample_acct()
    boost_now(DAO.get_random_1id(random_acct))
    SM.update(random_acct, 'func')

#######################################################
# きりぼっとのつぶやき
def lstm_tooter():
    seeds = DAO.get_least_10toots()
    #print('seeds',seeds)
    if len(seeds) <= 2:
        return
    seedtxt = "".join(seeds)
    spoiler = None
    gen_txt = kiri_deep.lstm_gentxt(seedtxt,num=3)
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
            #print('th_delete:',row)
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
        except Exception:
            kiri_util.error_log()

#######################################################
# 数取りゲーム
def th_gettingnum():
    gamenum = 100
    junbiTM = kiri_util.KiriTimer(3600)
    junbiTM.reset(0)
    gameTM = kiri_util.KiriTimer(240)
    while True:
        try:
            g_acct,g_id = GetNumQ.get()
            GetNum_flg.append('ON')
            if junbiTM.check() > 0:
                sleep(3)
                toot('@%s\n開催準備中だよー！あと%d分待ってねー！'%(g_acct,int(junbiTM.check()/60)), 'unlisted', g_id, None)
                sleep(27)
                continue

            #アクティブ人数確認
            i = DAO.get_gamenum()
            if  i <= 5:
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
            toot('🔸1〜%dの中から一番大きい数を取った人が勝ちだよー！\
                    \n🔸きりぼっとにメンション（ＤＭ可）で投票してね！\
                    \n🔸ただし、他の人と被ったら失格！\
                    \n🔸他の人と被らない最大の数を取った「一人」だけが勝ち！\
                    \n🔸制限時間は%d分だよー！はじめ！！\n#数取りゲーム #きりぼっと'%(gamenum,int(gameTM.check()/60)), 'public', None, '💸数取りゲーム（ミニ）始まるよー！🎮')
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

        except Exception:
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
            except Exception:
                #保存失敗したら、キューに詰めてリトライ！
                #StatusQ.put(status)
                kiri_util.error_log()
    except Exception:
        kiri_util.error_log()
        sleep(30)
        th_saver()

#######################################################
# ローカルタイムライン監視スレッド
def t_local():
    try:
        mastodon.stream_public(res_toot())
        #mastodon.stream_local(res_toot())
    except:
        kiri_util.error_log()
        sleep(30)
        t_local()

#######################################################
# ローカルタイムライン監視スレッド（認証なし）
def t_sub():
    try:
        publicdon.stream_local(public_listener())
    except:
        kiri_util.error_log()
        sleep(30)
        t_sub()

#######################################################
# ホームタイムライン監視スレッド
def t_user():
    try:
        mastodon.stream_user(men_toot())
    except:
        kiri_util.error_log()
        sleep(30)
        t_user()

#######################################################
# randomニコルくん
def th_nicoru():
    gen_txt = ''
    while len(gen_txt) < 430:
        gen_txt += ':nicoru{0}:'.format(random.randint(0,360))
    toot('@%s '%MASTER_ID + gen_txt, "direct", None, None)

#######################################################
# メイン
def main():
    threads = []
    #タイムライン受信系
    threads.append( threading.Thread(target=t_local ) ) #LTL
    #threads.append( threading.Thread(target=mastodon.stream_public,args=(res_toot(),) ) ) #FTL
    threads.append( threading.Thread(target=t_user ) ) #LTL
    threads.append( threading.Thread(target=t_sub ) ) #LTL
    #タイムライン応答系
    threads.append( threading.Thread(target=th_worker) )
    threads.append( threading.Thread(target=th_delete) )
    threads.append( threading.Thread(target=th_saver) )
    threads.append( threading.Thread(target=th_gettingnum) )
    threads.append( threading.Thread(target=th_quick) )
    #スケジュール起動系
    threads.append( threading.Thread(target=kiri_util.scheduler, args=(summarize_tooter,['02'])) )
    threads.append( threading.Thread(target=kiri_util.scheduler, args=(bottlemail_sending,['05'])) )
    threads.append( threading.Thread(target=kiri_util.scheduler, args=(monomane_tooter,None,30,0,5,CM)) )
    threads.append( threading.Thread(target=kiri_util.scheduler, args=(lstm_tooter,None,15,0,5,CM)) )
    threads.append( threading.Thread(target=kiri_util.scheduler, args=(timer_bst1st,None,45,0,5,CM)) )
    #threads.append( threading.Thread(target=kiri_util.scheduler, args=(th_nicoru,None,60,0,60,CM)) )

    for th in threads:
        th.start()
    for th in threads:
        th.join()

if __name__ == '__main__':
    main()
