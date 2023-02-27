# coding: utf-8
from mastodon import Mastodon, StreamListener
import re
import os
import random
import signal
import threading
import queue
from time import sleep
from pytz import timezone
import dateutil
from datetime import datetime, timedelta
from os.path import join
from collections import defaultdict, Counter
import wikipedia
from PIL import Image
import argparse

# きりぼコンフィグ
from kiribo.config import MEDIA_PATH, GOOGLE_ENGINE_KEY, GOOGLE_KEY, MASTODON_URL, MASTODON_ACCESS_TOKEN,\
    MASTER_ID, BOT_ID, BOT_LIST_PATH, KAOMOJI_PATH, KORA_PATH, HINPINED_WORDS_PATH,\
    WATCH_LIST_PATH, NADE_PATH, RECIPE_Z_PATH, RECIPE_A_PATH, NO_BOTTLE_PATH
    
# きりぼサブモジュール
from kiribo import bottlemail, cooling_manager, dao, deep, game, generate_text,\
    get_images_ggl, imaging, romasaga, scheduler, score_manager, stat, tenki,\
    timer, toot_summary, trans, util, haiku, tarot, bert

import logging
logger = logging.getLogger(__name__)

os.makedirs(MEDIA_PATH, exist_ok=True)

abc = list(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!?.()+-=,")
keisho = r"(くん|君|さん|様|さま|ちゃん|氏)"

wikipedia.set_lang("ja")
wikipedia.set_user_agent("kiri_bot (https://github.com/kiritan-pop/kiri_bot/)")

# Google画像検索設定
gi = get_images_ggl.GetImagesGGL(GOOGLE_KEY, GOOGLE_ENGINE_KEY)

#得点管理、流速監視
SM = score_manager.ScoreManager()
CM = cooling_manager.CoolingManager(15)
DAO = dao.Dao()
TRANS = trans.Trans(GOOGLE_KEY)
#しりとり用
StMG = game.Siritori_manager()

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
GetNumQ = util.ClearableQueue()
GetNumVoteQ = util.ClearableQueue()
GetNum_flg = []
HintPintoQ = util.ClearableQueue()
HintPinto_ansQ = util.ClearableQueue()
HintPinto_flg = []

slot_bal = []
toot_cnt = 0
TCNT_RESET = 15
acct_least_created_at = dict()

toots_for_rep = defaultdict(list)
toots_in_ltl = []

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
hanalist.append(f'🌷🌸🌹🌺🌻🌼大当たり！🌼🌻🌺🌹🌸🌷  @{MASTER_ID}')

jihou_dict = {
    "00": "🕛",
    "01": "🕐",
    "02": "🕑",
    "03": "🕒",
    "04": "🕓",
    "05": "🕔",
    "06": "🕕",
    "07": "🕖",
    "08": "🕗",
    "09": "🕘",
    "10": "🕙",
    "11": "🕚",
    "12": "🕛",
    "13": "🕐",
    "14": "🕑",
    "15": "🕒",
    "16": "🕓",
    "17": "🕔",
    "18": "🕕",
    "19": "🕖",
    "20": "🕗",
    "21": "🕘",
    "22": "🕙",
    "23": "🕚",
}

NN = '\n'

def get_args():
# アーギュメントのやつ
    parser = argparse.ArgumentParser()
    parser.add_argument("--gtime", type=int, default=30)
    parser.add_argument("--htime", type=int, default=20)
    args = parser.parse_args()
    return args


class notification_listener(StreamListener):
# マストドンＡＰＩ用部品を継承して、通知時の処理を実装ー！
    def on_notification(self, notification):
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        ymdhms = jst_now.strftime("%Y%m%d %H%M%S")

        if notification["type"] == "mention":
            status = notification["status"]
            CM.count(status['created_at'])
            WorkerQ.put(status)
            vote_check(status)
            logger.info(
                f"===notification mention from {notification['account']['acct']}「{util.content_cleanser(status['content'])[:100]}」")
        elif notification["type"] == "favourite":
            SM.update(notification["account"]["acct"], 'fav', ymdhms)
            logger.info(
                f"===notification favourite by {notification['account']['acct']}")
        elif notification["type"] == "reblog":
            SM.update(notification["account"]["acct"], 'boost', ymdhms)
            logger.info(
                f"===notification reblog by {notification['account']['acct']}")
        elif notification["type"] == "follow":
            SM.update(notification["account"]["acct"], 'boost', ymdhms)
            follow(notification["account"]["id"])
            logger.info(
                f"===notification follow by {notification['account']['acct']}")

    def on_update(self, status):
        # 時限トゥート用（自分のトゥートのみ）
        acct = status["account"]["acct"]
        if acct == BOT_ID:
            TimerDelQ.put(status)


class ltl_listener(StreamListener):
# マストドンＡＰＩ用部品を継承して、ローカルタイムライン受信時の処理を実装ー！
    def on_update(self, status):
        #mentionはnotificationで受けるのでLTLのはスルー！(｢・ω・)｢ 二重レス防止！
        if re.search(r'[^:]@' + BOT_ID, status['content']):
            return
        acct = status["account"]["acct"]
        if acct != BOT_ID:
            WorkerQ.put(status)


class public_listener(StreamListener):
# タイムライン保存用（認証なし）
    def on_update(self, status):
        StatusQ.put(status)
        CM.count(status['created_at'])
        acct = status["account"]["acct"]
        logger.info(
            f"「{util.content_cleanser(status['content'])[:30]:<30}」by {acct}")

    def on_delete(self, status_id):
        logger.info(f"===public_listener on_delete【{status_id}】===")
        DelQ.put(status_id)


def toot(toot_content: str, visibility: str = "direct", in_reply_to_id=None, spoiler_text: str = None, media_ids: list = None, interval=0, **kwargs):
    th = threading.Timer(interval=interval, function=PostQ.put,
                         args=((exe_toot, (toot_content, visibility, in_reply_to_id, spoiler_text, media_ids), kwargs),))
    th.start()


def exe_toot(toot_content:str, visibility:str="direct", in_reply_to_id=None, spoiler_text:str=None, media_ids:list=None, **kwargs):
    if spoiler_text:
        spo_len = len(spoiler_text)
    else:
        spo_len = 0

    try:
        mastodon.status_post(
            util.replace_ng_word(toot_content[0:490-spo_len]),
            visibility=visibility,
            in_reply_to_id=in_reply_to_id,
            spoiler_text=spoiler_text,
            media_ids=media_ids, **kwargs)
    except Exception as e:
        logger.error(e, exc_info=True)
        logger.error("POST リトライ")
        toot(toot_content, visibility, None, spoiler_text, media_ids, interval=4, **kwargs) 
    else:
       logger.info(f"🆕toot:{toot_content[0:300]}:{visibility}")


def fav_now(*args, **kwargs):  # ニコります
# ファボ処理
    PostQ.put((exe_fav_now, args, kwargs))


def exe_fav_now(id, *args, **kwargs):  # ニコります
    try:
        status = mastodon.status(id)
    except Exception as e:
        logger.error(e, exc_info=True)
    else:
        if status['favourited'] == False:
            sleep(0.2)
            mastodon.status_favourite(id)
            logger.info("🙆Fav")


def boost_now(*args, **kwargs):  # ぶーすと！
# ブースト
    PostQ.put((exe_boost_now, args, kwargs))


def exe_boost_now(id, *args, **kwargs):  # ぶーすと！
    try:
        status = mastodon.status(id)
    except Exception as e:
        logger.error(e, exc_info=True)
    else:
        if status['reblogged'] == False:
            mastodon.status_reblog(id)
        else:
            mastodon.status_unreblog(id)
            sleep(3)
            mastodon.status_reblog(id)
        logger.info("🙆boost")


def boocan_now(*args, **kwargs):  # ぶーすと！
# ブーキャン
    PostQ.put((exe_boocan_now, args, kwargs))


def exe_boocan_now(id, *args, **kwargs):  # ぶーすと！
    status = mastodon.status(id)
    if status['reblogged'] == True:
        mastodon.status_unreblog(id)
        logger.info("🙆unboost")


def follow(*args, **kwargs):
# フォロー
    PostQ.put((exe_follow, args, kwargs))


def exe_follow(id, *args, **kwargs):
    mastodon.account_follow(id)
    logger.info("💖follow")


def unfollow(*args, **kwargs):
# アンフォロー
    PostQ.put((exe_unfollow, args, kwargs))


def exe_unfollow(id, *args, **kwargs):
    mastodon.account_unfollow(id)
    logger.info("💔unfollow")


def toot_delete(*args, interval=5, **kwargs):
# トゥー消し
    th = threading.Timer(interval=interval, function=PostQ.put, args=((exe_toot_delete, args, kwargs),))
    th.start()


def exe_toot_delete(id, *args, **kwargs):
    mastodon.status_delete(id)
    logger.info("♥toot delete")


def vote_check(status):
# 数取りゲーム 投票前処理
    acct = status["account"]["acct"]
    id = status["id"]
    if re.search(r'[^:]@%s' % BOT_ID, status['content']):
        if len(util.hashtag(status['content'])) > 0:
            return
        content = util.content_cleanser(status['content'])
        if len(content) == 0:
            return
        if acct == 'twotwo' and re.search(r'!', content):
            if len(GetNum_flg) > 0:
                twocnt = content.count('トゥ')
                GetNumVoteQ.put([acct, id, int(101 - twocnt)])
            else:
                toot(f'@{acct}\n₍₍ ◝(◍•ᴗ•◍)◟⁾⁾今は数取りゲームしてないよ〜',
                     visibility='unlisted', in_reply_to_id=id)
        else:
            if len(GetNum_flg) > 0:
                if content.strip().isdigit():
                    GetNumVoteQ.put([acct, id, int(content.strip())])
            else:
                if content.strip().isdigit():
                    toot(f'@{acct}\n₍₍ ◝(◍•ᴗ•◍)◟⁾⁾今は数取りゲームしてないよ〜',
                         visibility='unlisted', in_reply_to_id=id)


def HintPinto_ans_check(status):
# ヒントでピント回答受付チェック
    acct = status["account"]["acct"]
    id = status["id"]
    content = util.content_cleanser(status['content'])
    if len(content) == 0 or acct == BOT_ID:
        return
    if len(HintPinto_flg) > 0:
        HintPinto_ansQ.put([acct, id, content.strip(), status["visibility"]])


def worker(status):
# ワーカー処理の実装
    HintPinto_ans_check(status)
    global toot_cnt
    id = status["id"]
    acct = status["account"]["acct"]
    username = "@" + acct
    visibility = status["visibility"]
    content = util.content_cleanser(status['content'])
    statuses_count = status["account"]["statuses_count"]
    spoiler_text = status["spoiler_text"]
    ac_created_at = status["account"]["created_at"]
    ac_created_at = ac_created_at.astimezone(timezone('Asia/Tokyo'))
    ac_ymd = ac_created_at.strftime("%Y%m%d")
    jst_now = datetime.now(timezone('Asia/Tokyo'))
    now_ymd = jst_now.strftime("%Y%m%d")
    media_attachments = status["media_attachments"]
    sensitive = status['sensitive']
    created_at = status['created_at']
    created_at = created_at.astimezone(timezone('Asia/Tokyo'))
    reply_to_acct_list = util.reply_to(status['content'])
    display_name = util.display_name_cleanser(status["account"]['display_name'])
    avatar_static = status["account"]['avatar_static']
    tags = status["tags"]

    #botはスルー
    if status["account"]["bot"]:
        return

    botlist = set([tmp.strip() for tmp in open(BOT_LIST_PATH).readlines(
    ) if os.path.exists(BOT_LIST_PATH) and len(tmp.strip()) > 0])
    botlist.add(BOT_ID)
    if acct in botlist:
        return

    Toot1bQ.put((content, acct))

    # 画像があればダウンロード
    media_file = []
    for media in media_attachments:
        media_file.append(util.download_media(media["url"]))
    media_file = [m for m in media_file if m]

    ct = max([int(CM.get_coolingtime()),0])

    # なでなで
    if acct in set([tmp.strip() for tmp in open(NADE_PATH).readlines() if os.path.exists(NADE_PATH) and len(tmp.strip()) > 0]):
        fav_now(id)

    # 定期トゥート
    if acct != BOT_ID and visibility == "public" and re.search(r'[^:]@%s' % BOT_ID, status['content']) is None:
        toots_in_ltl.append((content.strip(), created_at))

    # 高感度下げ
    if re.search(r"死ね", content+spoiler_text):
        SM.update(acct, 'func', score=-20)
    if re.search(r"^クソ|クソ$|[^ダ]クソ", content+spoiler_text):
        SM.update(acct, 'func', score=-3)

    # 定型文応答処理
    toot_now, id_now, vis_now, interval, reply = res_fixed_phrase(id, acct, username, visibility, content, statuses_count,
                                                               spoiler_text, ac_ymd, now_ymd, media_attachments,
                                                                  sensitive, created_at, reply_to_acct_list, ct)
    if toot_now:
        toot(reply + toot_now, vis_now, id_now, None, None, interval)
        return

    #各種機能
    if re.search(r"きりぼ.*(しりとり).*(しよ|やろ|おねがい|お願い)", content):
        # fav_now(id)
        if StMG.is_game(acct):
            toot(f'@{acct} 今やってる！\n※やめる場合は「しりとり終了」って言ってね', 'direct', id, None)
            return
        StMG.add_game(acct)
        SM.update(acct, 'func')
        word1, yomi1, tail1 = StMG.games[acct].random_choice()
        result, text = StMG.games[acct].judge(word1)
        toot(f'@{acct} 【Lv.{StMG.games[acct].lv}】じゃあ、{word1}【{yomi1}】の「{tail1}」！\n※このトゥートにリプしてね！\n※DMでお願いねー！',
             'direct',  id, None)

    elif StMG.is_game(acct) and re.search(r"(しりとり).*(終わ|おわ|終了|完了)", content) and visibility == 'direct':
        # fav_now(id)
        toot(
            f'@{acct} おつかれさまー！\n(ラリー数：{StMG.games[acct].rcnt})', 'direct',  id, None)
        StMG.end_game(acct)

    elif StMG.is_game(acct) and visibility == 'direct':
        # fav_now(id)
        word = str(content).strip()
        result, text = StMG.games[acct].judge(word)
        if result:
            if text == 'yes':
                ret_word, ret_yomi, tail = StMG.games[acct].get_word(word)
                if ret_word == None:
                    tmp_score = StMG.games[acct].rcnt*2+StMG.games[acct].lv
                    tmp_score //= 4
                    toot(
                        f'@{acct} う〜ん！思いつかないよー！負けたー！\n(ラリー数：{StMG.games[acct].rcnt}／{tmp_score}点獲得)', 'direct',  id, None)
                    SM.update(acct, 'getnum', score=tmp_score)
                    StMG.end_game(acct)
                else:
                    result2, text2 = StMG.games[acct].judge(ret_word)
                    if result2:
                        toot(
                            f'@{acct} {ret_word}【{ret_yomi}】の「{tail}」！\n(ラリー数：{StMG.games[acct].rcnt})\n※このトゥートにリプしてね！\n※DMでお願いねー！', 'direct',  id, None)
                    else:
                        tmp_score = StMG.games[acct].rcnt+StMG.games[acct].lv
                        tmp_score //= 2
                        toot(
                            f'@{acct} {ret_word}【{ret_yomi}】\n{text2}え〜ん負けたー！\n(ラリー数：{StMG.games[acct].rcnt}／{tmp_score}点獲得)', 'direct',  id, None)
                        SM.update(acct, 'getnum', score=tmp_score)
                        StMG.end_game(acct)
            else:
                #辞書にない場合
                toot(
                    f'@{acct} {text}\n※やめる場合は「しりとり終了」って言ってね！\n(ラリー数：{StMG.games[acct].rcnt})', 'direct',  id, None)
        else:
            toot(
                f'@{acct} {text}\nわーい勝ったー！\n(ラリー数：{StMG.games[acct].rcnt})', 'direct',  id, None)
            StMG.end_game(acct)

    elif re.search(r"[!！]スロット", content) and visibility == 'direct':
        # fav_now(id)
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
            toot(
                f'@{acct} 得点足りないよー！（所持：{acct_score}点／必要：{slot_rate*3}点）\nスロットミニや他のゲームで稼いでねー！', 'direct', in_reply_to_id=id)
            return
        #貪欲補正
        slot_bal.append(acct)
        if len(slot_bal) > 100:
            slot_bal.pop(0)
        reelsize += min([sum([1 for x in slot_bal if x == acct])//10, 5])
        #乱数補正
        reel_num += random.randint(-1, 1)
        reelsize += random.randint(-1, 1)
        reel_num = min([6, max([4, reel_num])])
        #得点消費
        SM.update(acct, 'getnum', score=- int(slot_rate*3))
        #スロット回転
        slot_accts = DAO.get_five(num=reel_num, minutes=120)
        slotgame = game.Friends_nico_slot(
            acct, slot_accts, slot_rate, reelsize)
        slot_rows, slot_score = slotgame.start()
        logger.debug(f'acct={acct} reel_num={reel_num} reelsize={reelsize}')
        sl_txt = ''
        for row in slot_rows:
            for c in row:
                sl_txt += c
            sl_txt += '\n'
        if slot_score > 0:
            SM.update(acct, 'getnum', score=slot_score)
            acct_score = SM.show(acct)[0][1]
            toot(f'@{acct}\n{sl_txt}🎯当たり〜！！{slot_score}点獲得したよー！！（{int(slot_rate*3)}点消費／合計{acct_score}点）', 'direct', in_reply_to_id=id)
        else:
            acct_score = SM.show(acct)[0][1]
            toot(
                f'@{acct}\n{sl_txt}ハズレ〜〜（{int(slot_rate*3)}点消費／合計{acct_score}点）', 'direct', in_reply_to_id=id)

    elif re.search(r"(ヒントでピント)[：:](.+)", content):
        if visibility == 'direct':
            word = re.search(r"(ヒントでピント)[：:](.+)",
                             str(content)).group(2).strip()
            if len(word) < 3:
                toot(f'@{acct} お題は３文字以上にしてね〜', 'direct', in_reply_to_id=id)
                return
            if len(word) > 30:
                toot(f'@{acct} お題は３０文字以下にしてね〜', 'direct', in_reply_to_id=id)
                return
            if util.is_ng(word):
                toot(f'@{acct} 気が向かないので別のお題にしてね〜', 'direct', in_reply_to_id=id)
                return
            HintPintoQ.put([acct, id, word])
            SM.update(acct, 'func')
        else:
            toot(f'@{acct} ＤＭで依頼してねー！周りの人に答え見えちゃうよー！', 'direct', in_reply_to_id=id)

    elif re.search(r"([ぼボ][とト][るル][メめ]ー[るル])([サさ]ー[ビび][スす])[：:]", content):
        logger.debug("★ボトルメールサービス")
        bottlemail_service(content=content, acct=acct, id=id, visibility=visibility)
        SM.update(acct, 'func')

    elif re.search(r"(きょう|今日)の.?(料理|りょうり)", content):
        recipe_service(content=content, acct=acct, id=id, visibility=visibility)
        SM.update(acct, 'func')

    elif re.search(r"(.+)って(何|なに|ナニ|誰|だれ|ダレ|いつ|どこ)\?$", content):
        word = re.search(r"(.+)って(何|なに|ナニ|誰|だれ|ダレ|いつ|どこ)\?$",
                         str(content)).group(1).strip()
        SM.update(acct, 'func')
        try:
            word = re.sub(
                r".*(へい)?きりぼ(っと)?(くん|君|さん|様|さま|ちゃん)?[!,.]?", "", word).strip()
            if len(word) == 0:
                return
            page = wikipedia.page(word)
        except wikipedia.exceptions.DisambiguationError as e:
            nl = "\n"
            toot(f'@{acct} 「{word}」にはいくつか意味があるみたいだよ〜{nl}次のいずれかのキーワードでもう一度調べてね〜{nl}{",".join(e.options)}', visibility, id, None)
        except Exception as e:
            logger.error(e, exc_info=True)
            toot(f'@{acct} え？「{word}」しらなーい！', visibility, id, None)
        else:
            summary_text = page.summary
            if len(acct) + len(summary_text) + len(page.url) > 450:
                summary_text = summary_text[0:450 -
                                            len(acct)-len(page.url)] + '……'
            toot(f'@{acct} {summary_text}\n{page.url}',
                 visibility, id, f'なになに？「{word}」とは……')

    elif len(media_attachments) > 0 and re.search(r"色[ぬ塗]って", content + spoiler_text):
        # fav_now(id)
        toot(f'@{acct} 色塗りサービスは終了したよ〜₍₍ ◝(╹ᗜ╹๑◝) ⁾⁾ ₍₍ (◟๑╹ᗜ╹)◟ ⁾⁾',
             visibility, id, None)

    elif len(media_attachments) > 0 and re.search(r"きりぼ.*アイコン作", content):
        SM.update(acct, 'func', score=1)
        if re.search(r"正月", content):
            mode = 0
        elif re.search(r"2|２", content):
            mode = 2
        else:
            mode = 1

        ret = imaging.newyear_icon_maker(media_file[0], mode=mode)
        if ret:
            media = mastodon.media_post(ret, 'image/gif')
            toot_now = f"@{acct} できたよ〜 \n ここでgifに変換するといいよ〜 https://www.aconvert.com/jp/video/mp4-to-gif/ \n#exp15m"
            toot(toot_now, visibility=visibility, in_reply_to_id=id, media_ids=[media])
        else:
            toot_now = f"@{acct} 透過画像じゃないとな〜"
            toot(toot_now, visibility=visibility, in_reply_to_id=id)

    elif len(media_attachments) > 0 and re.search(r"きりぼ.*透過して", content):
        SM.update(acct, 'func', score=1)
        alpha_image_path = imaging.auto_alpha(media_file[0], icon=False)
        media = mastodon.media_post(alpha_image_path, 'image/png')
        toot_now = f"@{acct} できたよ〜 \n#exp15m"
        toot(toot_now, visibility=visibility, in_reply_to_id=id, media_ids=[media])

    elif re.search(r"([わワ][てテ]|拙僧|小職|私|[わワ][たタ][しシ]|[わワ][たタ][くク][しシ]|自分|僕|[ぼボ][くク]|俺|[オお][レれ]|朕|ちん|余|[アあ][タた][シし]|ミー|あちき|あちし|あたち|[あア][たタ][いイ]|[わワ][いイ]|わっち|おいどん|[わワ][しシ]|[うウ][ちチ]|[おオ][らラ]|儂|[おオ][いイ][らラ]|あだす|某|麿|拙者|小生|あっし|手前|吾輩|我輩|わらわ|妾|ぅゅ|のどに|ちゃそ)の(ランク|ランキング|順位|スコア|成績|せいせき|らんく|らんきんぐ|すこあ)", content):
        show_rank(acct=acct, target=acct, id=id, visibility=visibility)
        SM.update(acct, 'func')

    elif re.search(r":@(.+):.*の(ランク|ランキング|順位|スコア|成績|せいせき|らんく|らんきんぐ|すこあ)", content):
        word = re.search(
            r":@(.+):.*の(ランク|ランキング|順位|スコア|成績|せいせき|らんく|らんきんぐ|すこあ)", str(content)).group(1)
        show_rank(acct=acct, target=word, id=id, visibility=visibility)
        SM.update(acct, 'func')
    elif re.search(r"(数取りゲーム|かずとりげぇむ).*(おねがい|お願い)", content):
        logger.debug('数取りゲーム受信')
        if len(GetNum_flg) > 0:
            toot(f"@{acct} 数取りゲーム開催中だよー！急いで投票してー！", 'public', id)
        else:
            # fav_now(id)
            GetNumQ.put([acct, id])
            SM.update(acct, 'func')

    elif '?トゥトゥトゥ' in content and acct == 'twotwo':  # ネイティオ専用
        if len(GetNum_flg) > 0:
            toot(f"@{acct} 数取りゲーム開催中だよー！急いで投票してー！", 'public', id)
        else:
            GetNumQ.put([acct, id])
            SM.update(acct, 'func')

    elif len(content) > 140 and len(content) * 0.8 < sum([v for k, v in Counter(content).items() if k in abc]):
        # fav_now(id)
        lang = TRANS.detect(content)
        if lang and lang != 'ja':
            toot_now = TRANS.xx2ja(lang, content)
            if toot_now:
                if re.search(r"[^:]@|^@", toot_now):
                    pass
                else:
                    toot_now = f"@{acct}\n{toot_now}\n#きり翻訳 #きりぼっと"
                    toot(toot_now, 'public', id, f'翻訳したよ〜！なになに……？ :@{acct}: ＜')
                    SM.update(acct, 'func')

    elif '翻訳して' in spoiler_text:
        # fav_now(id)
        toot_now = TRANS.ja2en(content)
        if toot_now:
            if re.search(r"[^:]@|^@", toot_now):
                pass
            else:
                toot_now = f"@{acct}\n{toot_now}\n#きり翻訳 #きりぼっと"
                toot(toot_now, 'public', id, f'翻訳したよ〜！ :@{acct}: ＜')
                SM.update(acct, 'func')

    elif len(content) > 140 and len(spoiler_text) == 0:
        gen_txt = toot_summary.summarize(content, limit=10, lmtpcs=1, m=1, f=4)
        if gen_txt[-1] == '#':
            gen_txt = gen_txt[:-1]
        logger.debug(f'★要約結果：{gen_txt}')
        if util.is_japanese(gen_txt):
            if len(gen_txt) > 5:
                gen_txt += "\n#きり要約 #きりぼっと"
                toot("@" + acct + " :@" + acct + ":\n" +
                     gen_txt, visibility, id, "勝手に要約サービス")

    elif re.search(r"きりぼ.+:@(.+):.*の初", content):
        target = re.search(r"きりぼ.+:@(.+):.*の初", str(content)).group(1)
        toots = DAO.get_user_toots(target)
        # トゥートの存在チェック
        check_fg = False
        for tid, tcontent, tdate, ttime in toots:
            try:
                status = mastodon.status(tid)
            except Exception as e:
                logger.error(e, exc_info=True)
                sleep(2)
                continue
            else:
                check_fg = True
                tdate = f'{tdate:08d}'
                ttime = f'{ttime:06d}'
                ymdhms = f'on {tdate[:4]}/{tdate[4:6]}/{tdate[6:]} at {ttime[:2]}:{ttime[2:4]}:{ttime[4:]}'
                tcontent = util.content_cleanser(tcontent)
                sptxt = f":@{target}: の初トゥートは……"
                body = f"@{acct} \n"
                body += f":@{target}: ＜{tcontent} \n {ymdhms} \n"
                body += f"{MASTODON_URL}/@{target}/{tid}"
                toot(body, visibility=visibility, in_reply_to_id=id, spoiler_text=sptxt)
                break
        if check_fg == False:
            body = f"@{acct} 見つからなかったよ〜😢"
            toot(body, visibility=visibility, in_reply_to_id=id)

    elif re.search(r"きりぼ(くん|君|さん|様|さま|ちゃん)?[!！、\s]?きりたん丼の(天気|状態|状況|ステータス|status).*(おしえて|教えて|おせーて)?|^!server.*stat", content):
        stats = stat.sys_stat()
        logger.debug(f"stats={stats}")
        toot(
            f"@{acct} \nただいまの気温{stats['cpu_temp']}℃、忙しさ{stats['cpu']:.1f}％、気持ちの余裕{stats['mem_available']/(10**9):.1f}GB、懐の広さ{stats['disk_usage']/(10**9):.1f}GB", visibility=visibility, in_reply_to_id=id)

    elif re.search(r"きりぼ(くん|君|さん|様|さま|ちゃん)?[!！、\s]?.+の天気.*(おしえて|教え|おせーて)?", content):
        tenki_area = re.search(
            r"きりぼ(くん|君|さん|様|さま|ちゃん)?[!！、\s]?(.+)の天気.*(おしえて|教え|おせーて)?", str(content)).group(2).strip()

        retcode, weather_image_path = tenki.make_forecast_image(quary=tenki_area)
        if retcode == 9:
            toot(f"@{acct} 知らない場所の天気はわからないよ〜", visibility=visibility, in_reply_to_id=id)
        elif retcode == 2:
            toot(f"@{acct} 複数地名が見つかったので、次の地名でもっかい呼んでみてー\n{'、'.join(weather_image_path)}",
                 visibility=visibility, in_reply_to_id=id)
        else:
            toot_now = f"@{acct}\n(C) 天気予報 API（livedoor 天気互換）\n気象庁 Japan Meteorological Agency\n気象庁 HP にて配信されている天気予報を JSON データへ編集しています。"
            media_files = []
            media_files.append(mastodon.media_post(weather_image_path, 'image/png'))
            toot(toot_now, visibility=visibility, in_reply_to_id=id, media_ids=media_files, spoiler_text=f"{tenki_area}に関する天気だよ〜")

    elif re.search(r"!tarot|きりぼ(くん|君|さん|様|さま|ちゃん)?[!！、\s]?(占って|占い|占う|占え)", content):
        if tarot.tarot_check(acct):
            text, tarot_result = tarot.tarot_main()
            img_path = tarot.make_tarot_image(tarot_result, avatar_static)
            media_files = []
            media_files.append(
                mastodon.media_post(img_path, 'image/png'))
            toot(f"@{acct}\n{text}", visibility=visibility, in_reply_to_id=id,
                 spoiler_text=f":@{acct}: を占ったよ〜", media_ids=media_files)
        else:
            toot(f"@{acct} 前回占ったばっかりなので、もう少し舞っててね〜", visibility=visibility, in_reply_to_id=id)

    elif re.search(r'[^:]@%s' % BOT_ID, status['content']):
        SM.update(acct, 'reply')
        if content.strip().isdigit():
            return
        if len(content) == 0:
            return
        # fav_now(id)
        toots_for_rep[acct].append((content.strip(), created_at))
        seeds = [] #toots_in_ltl[-20:]
        seeds.extend(toots_for_rep[acct])
        #時系列ソート
        seeds.sort(key=lambda x: (x[1]))
        threading.Thread(target=dnn_gen_toot_sub, args=(
            acct, seeds, visibility, id, toots_for_rep)).start()

    elif re.search(r"(きり|キリ).*(ぼっと|ボット|[bB][oO][tT])|[きキ][りリ][ぼボ]|[きキ][りリ][ぽポ][っッ][ぽポ]", content + spoiler_text) != None \
        and re.search(r"^[こコ][らラ][きキ][りリ][ぼボぽポ]", content + spoiler_text) == None:
        SM.update(acct, 'reply')
        if random.randint(0, 10+ct) > 9:
            return
        # fav_now(id)
        seeds = toots_in_ltl[-20:]
        threading.Thread(target=dnn_gen_toot_sub, args=(
            acct, seeds, visibility, id)).start()
        SM.update(acct, 'reply')

    elif sensitive == False and len(media_file) > 0:
        toot_now, attach_files = ana_image(media_file, acct)
        if len(toot_now) > 0:
            if len(attach_files) > 0:
                toot_now = "#exp15m"
                toot(toot_now, visibility=visibility, in_reply_to_id=None,
                     spoiler_text='おわかりいただけるだろうか……', media_ids=attach_files, interval=5)
            else:
                toot(toot_now, visibility=visibility)

    else:
        if re.search(r'[a-zA-Z0-9!-/:-@¥[-`{-~]', content) == None and len(tags) == 0 and len(content.replace('\n', '')) > 5:
            ikku = haiku.Reviewer()
            song = ikku.find_just(content.replace('\n', ''))
            if song:
                media_files = []
                media_files.append(
                    mastodon.media_post(haiku.make_ikku_image(song, avatar_static), 'image/png'))
                toot(
                    f"{NN.join([''.join([node.surface for node in phrase]) for phrase in song.phrases])}{NN}{'　'*4}:@{acct}:{display_name} {'（季語：'+song.season_word+'）' if song.season_word else ''}",
                    spoiler_text=f"{'俳句' if song.season_word else '川柳'}を検出したよ〜", visibility=visibility, media_ids=media_files)

def res_fixed_phrase(id, acct, username, visibility, content, statuses_count,
                    spoiler_text, ac_ymd, now_ymd, media_attachments,
                    sensitive, created_at, reply_to_acct_list, ct):
# 定型文応答処理

    def re_search_rnd(re_txt, text, threshold=None, flags=0):
        rnd = random.randint(0, ct+6)
        if acct == MASTER_ID:
            rnd = 0
        if re.search(re_txt, text, flags=flags) != None:
            if threshold == None:
                return True
            elif rnd <= threshold:
                return True
        return False

    toot_now = ''
    vis_now = visibility
    interval = 0
    reply = f"@{acct} " if BOT_ID in reply_to_acct_list else ""
    id_now = id if reply != "" else None

    if Toot1bQ.empty():
        content_1b, acct_1b = None, None
    else:
        content_1b, acct_1b = Toot1bQ.get()  # キューから１回前を取得

    if re_search_rnd(r"^貞$", content, 8):
        if content_1b != None and acct == acct_1b:
            SM.update(acct, 'func', score=-1)
            if re_search_rnd(r"^治$", content_1b, 8):
                SM.update(acct, 'func', score=2)
                toot_now = '　　三(  っ˃̵ᴗ˂̵) 通りまーす！'

    #ネイティオが半角スペース区切りで５つ以上あれば翻訳
    if (acct == MASTER_ID or acct == 'twotwo') and len(content.split(' ')) > 4 and content.count('トゥ') > 4 and content.count('ー') > 0:
        toot_now = f':@{acct}: ＜「{util.two2jp(content)}」'
        SM.update(acct, 'func')
    if statuses_count != 0 and statuses_count % 10000 == 0:
        interval = 180
        toot_now = username + "\n"
        toot_now += f"あ！そういえばさっき{statuses_count:,}トゥートだったよー！"
        SM.update(acct, 'func')
    elif statuses_count == 1 and ac_ymd == now_ymd:
        interval = 5
        toot_now = username + "\n"
        toot_now += "新規さんいらっしゃーい！🍵🍡どうぞー！"
        vis_now = 'unlisted'
        SM.update(acct, 'func')
    elif re_search_rnd(r"草$", content+spoiler_text, 1):
        SM.update(acct, 'func', score=-1)
        toot_now = random.choice(hanalist)  # + ' 三💨 ﾋﾟｭﾝ!!'
    elif re_search_rnd(r"花$", content+spoiler_text, 1):
        SM.update(acct, 'func')
        tmp = []
        tmp.append('木')
        tmp.append('森')
        tmp.append('種')
        toot_now = random.choice(tmp)
    elif re_search_rnd(r"^:twitter:.+(((🔥)))$", content, 4, flags=(re.MULTILINE | re.DOTALL)):
        SM.update(acct, 'func')
        tmp = []
        tmp.append(':twitter: ＜ﾊﾟﾀﾊﾟﾀｰ\n川\n\n(((🔥)))')
        tmp.append('(ﾉ・_・)ﾉ ﾆｹﾞﾃ!⌒:twitter: ＜ｱﾘｶﾞﾄｩ!\n(((🔥)))')
        tmp.append('(ﾉ・_・)ﾉ ﾆｹﾞﾃ!⌒🍗 ＜ｱﾘｶﾞﾄｩ!\n(((🔥)))')
        toot_now = random.choice(tmp)
    elif re_search_rnd(r"ブリブリ|ぶりぶり|うん[ちこ]|💩", content+spoiler_text, 4):
        SM.update(acct, 'func', score=-2)
        tmp = []
        tmp.append(f":@{acct}: " + r'{{{🌊🌊🌊🌊}}} ＜ざばーっ！')
        tmp.append('( •́ฅ•̀ )ｸｯｻ')
        tmp.append(f"　:@{acct}:\nっ🚽")
        toot_now = random.choice(tmp)
    elif re_search_rnd(r"^木$|^林$|^森$", content+spoiler_text, 4):
        SM.update(acct, 'func')
        tmp = []
        tmp.append(r'{{{🌴🌴🌴🌴}}} ＜すくすくーっ！')
        tmp.append(r'{{{🌲🌲🌲🌲}}} ＜すくすくーっ！')
        tmp.append(r'{{{🌳🌳🌳🌳}}} ＜すくすくーっ！')
        toot_now = random.choice(tmp)
    elif re_search_rnd(r"^流して$|^水$", content+spoiler_text, 4):
        SM.update(acct, 'func')
        toot_now = r'{{{🌊🌊🌊🌊}}} ＜ざばーっ！'
    elif re_search_rnd(r"^ふきふき$|^竜巻$|^風$", content, 4):
        SM.update(acct, 'func')
        tmp = []
        tmp.append('(((🌪🌪🌪🌪)))＜ごぉ〜〜っ！')
        tmp.append('(((💨💨💨)))[[[🍃]]]＜ぴゅ〜〜っ！')
        toot_now = random.choice(tmp)
    elif re_search_rnd(r"^凍らせて$|^氷$", content, 2):
        SM.update(acct, 'func')
        toot_now = '[[[❄]]][[[❄]]][[[❄]]][[[❄]]][[[❄]]] ＜カチコチ〜ッ！'
    elif re_search_rnd(r"^雷$", content, 2):
        SM.update(acct, 'func')
        toot_now = r'{{{⚡⚡⚡⚡}}}＜ゴロゴロ〜ッ！'
    elif re_search_rnd(r"^雲$", content, 2):
        SM.update(acct, 'func')
        toot_now = r'(((☁☁☁☁)))＜もくもく〜'
    elif re_search_rnd(r"^雨$", content, 2):
        SM.update(acct, 'func')
        toot_now = r'(((☔☔☔☔)))＜ざーざー'
    elif re_search_rnd(r"^雪$", content, 2):
        SM.update(acct, 'func')
        toot_now = r'[[[❄]]][[[❄]]][[[❄]]][[[❄]]][[[❄]]]＜こんこん〜'
    elif re_search_rnd(r"^ぬるぽ$|^[Nn]ull[Pp]ointer[Ee]xception$", content, 4):
        SM.update(acct, 'func', score=-1)
        toot_now = 'ｷﾘｯ'
    elif re_search_rnd(r"^通過$", content, 4):
        SM.update(acct, 'func')
        tmp = []
        tmp.append('⊂(˃̵᎑˂̵๑⊃ )彡　阻止！')
        tmp.append('　ミ(  っ˃̵ᴗ˂̵)っ　阻止！')
        toot_now = random.choice(tmp)
    elif re_search_rnd(r"3.{0,1}3.{0,1}4", content, 4):
        SM.update(acct, 'func', score=-1)
        toot_now = 'ﾅﾝ :nan:'
    elif re_search_rnd(r"^ちくわ大明神$", content, 4):
        SM.update(acct, 'func', score=-1)
        toot_now = 'ﾀﾞｯ'
    elif re_search_rnd(r"ボロン$|ぼろん$", content, 2):
        SM.update(acct, 'func', score=-2)
        toot_now = f':@{acct}: ✂️チョキン！！'
    elif re_search_rnd(r"さむい$|寒い$", content, 2):
        SM.update(acct, 'func', score=-1)
        toot_now = f'(((🔥)))(((🔥)))(((🔥)))\n(((🔥))):@{acct}:(((🔥)))\n(((🔥)))(((🔥)))(((🔥))) '
    elif re_search_rnd(r"あつい$|暑い$", content, 2):
        SM.update(acct, 'func', score=-1)
        toot_now = f'[[[❄]]][[[❄]]][[[❄]]]\n[[[❄]]]:@{acct}:[[[❄]]]\n[[[❄]]][[[❄]]][[[❄]]] '
    elif re_search_rnd(r"^(今|いま)の[な|無|ナ][し|シ]$", content, 4):
        SM.update(acct, 'func', score=-1)
        toot_now = f':@{acct}: 🚓🚓🚓＜う〜う〜！いまのなし警察でーす！'
    elif re_search_rnd(r"ツイッター|ツイート|[tT]witter", content, 1):
        SM.update(acct, 'func', score=-1)
        if random.randint(0,10)%2 ==0:
            toot_now = 'つ、つつつ、つい〜〜！！？！？？！？！'
        else:
            toot_now = 'つい〜……'
    elif re_search_rnd(r"[な撫]でて", content):
        fav_now(id)
        SM.update(acct, 'reply')
    elif re_search_rnd(r"なんでも|何でも", content, 2):
        SM.update(acct, 'func', score=-1)
        toot_now = 'ん？'
    elif re_search_rnd(r"泣いてる|泣いた|涙が出[るた(そう)]", content, 2):
        SM.update(acct, 'func')
        toot_now = f'( *ˊᵕˋ)ﾉ :@{acct}: ﾅﾃﾞﾅﾃﾞ'
    elif re_search_rnd(r"^桐乃じゃないが$", content+spoiler_text, 2):
        SM.update(acct, 'func')
        toot_now = f'桐乃じゃないね〜'
    elif re_search_rnd(r"^.+じゃないが$", content+spoiler_text, 2):
        word = re.search(r"^(.+)じゃないが$", content+spoiler_text).group(1)
        SM.update(acct, 'func')
        toot_now = f'{word}じゃが！'
    elif re_search_rnd(r"惚気|ほっけ|ホッケ", content+spoiler_text, 2):
        SM.update(acct, 'func', score=-1)
        toot_now = '(((🔥🔥🔥🔥)))＜ごぉぉぉっ！'
    elif re_search_rnd(r"^燃やして$|^火$|^炎$", content+spoiler_text, 4):
        SM.update(acct, 'func')
        toot_now = '(((🔥🔥🔥🔥)))＜ごぉぉぉっ！'
    elif re_search_rnd(r"[ご御夕昼朝][食飯][食た]べ[よるた]|(腹|はら)[へ減]った|お(腹|なか)[空す]いた|(何|なに)[食た]べよ", content, 3):
        SM.update(acct, 'func')
        recipe_service(content=content, acct=acct, id=id, visibility=visibility)
    elif re_search_rnd(r"^.+じゃね[ぇえ]ぞ", content+spoiler_text, 4):
        word = re.search(r"^(.+)じゃね[ぇえ]ぞ", content+spoiler_text).group(1)
        SM.update(acct, 'func')
        if len(word) <= 5:
            toot_now = f'{word}じゃぞ……{{{{{{💃}}}}}}'
    elif re_search_rnd(r"止まるんじゃね[ぇえ]ぞ", content+spoiler_text, 4):
        SM.update(acct, 'func')
        toot_now = r'止まるんじゃぞ……{{{💃}}}'
    elif re_search_rnd(r"[おぉ][じぢ]|[おぉ][じぢ]さん", content+spoiler_text, 4):
        SM.update(acct, 'func')
        tmp = []
        tmp.append('٩(`^´๑ )۶三٩(๑`^´๑)۶三٩( ๑`^´)۶')
        tmp.append('٩(`^´๑ )۶三٩( ๑`^´)۶')
        tmp.append(' ₍₍ ٩(๑`^´๑)۶ ⁾⁾ぉぢぉぢダンスーー♪')
        tmp.append('٩(٩`^´๑ )三( ๑`^´۶)۶')
        toot_now = random.choice(tmp)
    elif re_search_rnd(r"^う$", content, 6):
        SM.update(acct, 'func')
        toot_now = 'え'
    elif re_search_rnd(r"^うっ$", content, 6):
        SM.update(acct, 'func')
        toot_now = 'えっ'
    elif re_search_rnd(r"^は？$", content, 6):
        SM.update(acct, 'func')
        toot_now = 'ひ？'
    elif "マストドン閉じろ" in content:
        toot_now = 'はい'
        interval = random.uniform(0.01, 0.7)
    elif "(ง ˆᴗˆ)ว" in content:
        SM.update(acct, 'func')
        toot_now = '◝( ・_・)◟ <ﾋﾟﾀｯ!'
    elif re_search_rnd(r".+とかけまして.+と[と解]きます|.+とかけて.+と[と解]く$", content):
        SM.update(acct, 'func', score=2)
        toot_now = 'その心は？'
        interval = 1
    elif re_search_rnd(r"^しばちゃんは.+[\?？]$", content) and acct in ['Ko4ba', MASTER_ID]:
        SM.update(acct, 'func')
        toot_now = '＼絶好調に美少女ー！／'
        interval = 1
    elif re_search_rnd(r"^きりたんは.+[\?？]$", content) and acct == MASTER_ID:
        SM.update(acct, 'func')
        toot_now = '＼そこにいるー！／'
        interval = 1
    elif re_search_rnd(r"^あのねあのね", content, 6):
        SM.update(acct, 'func')
        toot_now = 'なになにー？'
        interval = 0
    elif re_search_rnd(r"パソコンつけ", content) and acct == "12":
            SM.update(acct, 'func')
            if random.randint(0,10) % 2 == 0:
                toot_now = '!お年玉'
            else:
                toot_now = '!おみくじ10連'
            interval = 8
    elif re_search_rnd("寝(ます|る|マス)([よかぞね]?|[…。うぅー～！・]+)$|^寝(ます|る|よ)[…。うぅー～！・]*$|\
                    寝(ます|る|マス)(.*)[ぽお]や[ユすしー]|きりぼ(.*)[ぽお]や[ユすしー]", content):
        if not re_search_rnd("寝る(かた|方|人|ひと|民)", content):
            toot_now = f":@{acct}: おやすみ〜 {random.choice([tmp.strip() for tmp in open(KAOMOJI_PATH,'r').readlines() if os.path.exists(KAOMOJI_PATH) and len(tmp.strip())>0])}\n#挨拶部"
            interval = 5
    elif re_search_rnd(r"^[こコ][らラ][きキ][りリ][ぼボぽポ]", content):
        toot_now = random.choice([tmp.strip() for tmp in open(KORA_PATH, 'r').readlines() if os.path.exists(KORA_PATH) and len(tmp.strip()) > 0])

    elif re_search_rnd(r"[へヘはハ][くク].*[しシ][ょョ][んン].*[出でデ][たタ]", content, 3):
        r = max([0, int(random.gauss(30, 30))])
        maoudict = {"大魔王": 100, "中魔王": 10, "小魔王": 1}
        result = {}
        for k, v in maoudict.items():
            if r >= v:
                result[k] = int(r//v)
                r = r % v
        if len(result) > 0:
            toot_now = f":@{acct}: 只今の記録"
            for k, v in result.items():
                toot_now += f"、{k}:{v}"
            toot_now += "、でした〜\n#魔王チャレンジ"
            if "大魔王" in result.keys():
                toot_now += " #大魔王"
        else:
            toot_now = f":@{acct}: 只今の記録、０魔王でした〜\n#魔王チャレンジ"
    
    elif re_search_rnd(r"(.+)[出でデ][たタ].?$", content, 2):
        r = max([0, int(random.gauss(30, 30))])
        maoudict = {"大魔王": 100, "中魔王": 10, "小魔王": 1}
        word = re.search(r"(.+)[出でデ][たタ].?$", str(content)).group(1).strip()
        wakati_list = deep.tagger.parse(word).strip().split()
        wakati_list = [w for w in wakati_list if len(w) > 1]
        if len(wakati_list) > 0:
            word = sorted([(s, len(s))
                        for s in wakati_list], key=lambda x: -x[1])[0][0]
            result = {}
            for k, v in maoudict.items():
                if r >= v:
                    result[k] = int(r//v)
                    r = r % v
            if len(result) > 0:
                toot_now = f":@{acct}: 只今の記録"
                for k, v in result.items():
                    toot_now += f"、{word}{k}:{v}"
                toot_now += f"、でした〜\n#{word}魔王チャレンジ"
                if "大魔王" in result.keys():
                    toot_now += " #大魔王"
            else:
                toot_now = f":@{acct}: 只今の記録、０{word}魔王でした〜\n#{word}魔王チャレンジ"

    return toot_now, id_now, vis_now, interval, reply


def ana_image(media_file, acct):
# 画像判定
    toot_now = ''
    attach_files = []
    logger.debug(media_file)
    for f in media_file:
        result = deep.takoramen(f)
        logger.debug(result)
        if result in ['風景', '夜景', 'other']:
            tmp = imaging.face_search(f)
            if tmp:
                ex = tmp.rsplit('.')[-1]
                if ex == 'jpg':
                    ex = 'jpeg'
                attach_files.append(mastodon.media_post(tmp, 'image/' + ex))
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
        elif result in ['汚部屋', '部屋', '自撮り', '太もも']:
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
            toot_now += 'るの人だ！'
        elif result == '東北ずん子':
            toot_now += '{{{:zunda:}}}ずんだもち！'
        elif result == '東北イタコ':
            toot_now += 'タコ姉！'
        elif result == '東北きりたん':
            toot_now += '{{{:kiritampo:}}}きりたんぽ！'
        elif result == 'スクショ':
            if random.randint(0, 4) == 0:
                toot_now += '📷スクショパシャパシャ！'
        else:
            if 'チョコ' in result or 'ショコラ' in result:
                toot_now += f':@{acct}: 🚓🚓🚓＜う〜う〜！飯テロ警察 チョコレート係でーす！'
            else:
                toot_now += f':@{acct}: 🚓🚓🚓＜う〜う〜！飯テロ警察 {result}係でーす！'
            break

    return toot_now.strip(), attach_files


def business_contact(status):
# 認証なしタイムライン用（きりぼがブロックされてても反応する用）
    id = status["id"]
    acct = status["account"]["acct"]
    content = util.content_cleanser(status['content'])
    statuses_count = status["account"]["statuses_count"]
    created_at = status['created_at']
    display_name = util.display_name_cleanser(status["account"]['display_name'])
    ac_created_at = status["account"]["created_at"]
    ac_created_at = ac_created_at.astimezone(timezone('Asia/Tokyo'))

    if re.search(r"^(緊急|強制)(停止|終了|再起動)$", content) and acct == MASTER_ID:
        logger.warn("＊＊＊＊＊＊＊＊＊＊＊緊急停止したよー！＊＊＊＊＊＊＊＊＊＊＊")
        toot(f"@{MASTER_ID} 緊急停止しまーす！", 'direct', id, None)
        sleep(10)
        os.kill(os.getpid(), signal.SIGKILL)

    if '@' in acct:  # 連合スルー
        return
    #最後にトゥートしてから3時間以上？
    if acct in acct_least_created_at:
        ymdhms = acct_least_created_at[acct]
    else:
        ymdhms = DAO.get_least_created_at(acct)

    acct_least_created_at[acct] = created_at
    diff = timedelta(hours=3)

    jst_now = datetime.now(timezone('Asia/Tokyo'))
    jst_now_hh = int(jst_now.strftime("%H"))

    kaomoji = random.choice([tmp.strip() for tmp in open(KAOMOJI_PATH, 'r').readlines() if os.path.exists(KAOMOJI_PATH) and len(tmp.strip()) > 0])
    if statuses_count == 1:
        toot_now = f':@{acct}: （{display_name}）ご新規さんかもー！{kaomoji}\n #挨拶部'
        toot(toot_now, visibility='public', interval=3)
    elif ymdhms == None or ymdhms + diff < created_at:
        logger.info(f"ymdhms={ymdhms}, created={created_at}, acct_least_created_at[acct]={acct_least_created_at[acct]}, dao={DAO.get_least_created_at(acct)}")
        aisatsu = "おかえり〜！"
        bure = random.randint(-1, 1)
        if 0 <= jst_now_hh <= 3 + bure:
            aisatsu = "こんばんは〜！"
        elif 5 <= jst_now_hh <= 11 + bure:
            aisatsu = "おはよ〜！"
        elif 12 <= jst_now_hh <= 17 + bure:
            aisatsu = "こんにちは〜！"
        elif 19 <= jst_now_hh <= 24:
            aisatsu = "こんばんは〜！"

        toot_now = f':@{acct}: {display_name}\n{aisatsu} {kaomoji}\n #挨拶部'
        toot(toot_now, visibility='public', interval=3)

    watch_list = set([tmp.strip() for tmp in open(WATCH_LIST_PATH).readlines(
    ) if os.path.exists(WATCH_LIST_PATH) and len(tmp.strip()) > 0])
    if acct in watch_list:
        toot_now = f'@{MASTER_ID}\n:@{acct}: {display_name}\n「{content}」\n#exp10m'
        toot(toot_now, visibility='direct')


def recipe_service(content=None, acct=MASTER_ID, id=None, visibility='unlisted'):
# レシピ提案
    # fav_now(id)
    generator = generate_text.GenerateText(1)
    #料理名を取得ー！
    gen_txt = ''
    spoiler = generator.generate("recipe")

    #材料と分量を取得ー！
    zairyos = []
    amounts = []
    for line in open(RECIPE_Z_PATH, 'r'):
        zairyos.append(line.strip())
    for line in open(RECIPE_A_PATH, 'r'):
        amounts.append(line.strip())
    zairyos = random.sample(zairyos, 4)
    amounts = random.sample(amounts, 4)
    gen_txt += '＜材料＞\n'
    for z, a in zip(zairyos, amounts):
        gen_txt += ' ・' + z + '\t' + a + '\n'

    #作り方を取得ー！途中の手順と終了手順を分けて取得するよー！
    text_chu = []
    text_end = []
    generator = generate_text.GenerateText(50)
    while len(text_chu) <= 3 or len(text_end) < 1:
        tmp_texts = generator.generate("recipe_text").split('\n')
        for tmp_text in tmp_texts:
            if re.search(r'完成|出来上|召し上が|できあがり|最後|終わり', tmp_text):
                if len(text_end) <= 0:
                    text_end.append(tmp_text)
            else:
                if len(text_chu) <= 3:
                    text_chu.append(tmp_text)
    text_chu.extend(text_end)
    gen_txt += '＜作り方＞\n'
    for i, text in enumerate(text_chu):
        gen_txt += f' {i+1}. {text}\n'
    gen_txt = f"@{acct}\n{gen_txt}\n#きり料理提案サービス #きりぼっと"
    toot(gen_txt, visibility, id, f":@{acct}: {spoiler}")


def show_rank(acct=None, target=None, id=None, visibility=None):
# ランク表示
    ############################################################
    # 数取りゲームスコアなど
    logger.debug(f"show_rank target={target}")
    # if id:
    #     fav_now(id)
    sm = score_manager.ScoreManager()
    score = defaultdict(int)
    like = defaultdict(int)

    for row in sm.show():
        # if row[1] > 0:
        score[row[0]] = row[1]
        like[row[0]] = row[2] + row[4] + row[6] + row[7]

    if acct:
        score_rank = 0
        for i, (k, v) in enumerate( sorted(score.items(), key=lambda x: -x[1])):
            if k == target:
                score_rank = i + 1
                break

        like_rank = 0
        for i, (k, v) in enumerate( sorted(like.items(), key=lambda x: -x[1])):
            if k == target:
                like_rank = i + 1
                break

        toot_now = f"@{acct}\n:@{target}: のスコアは……\n"
        toot_now += f"ゲーム得点：{score[target]:>4}点({score_rank}/{len(score)}位)\nきりぼっと好感度：{like[target]:>4}点({like_rank}/{len(like)}位)"

        hours = [1, 24] #,24*31]
        coms = ["時間", "日　"]  #,"ヶ月"]
        for hr, com in zip(hours, coms):
            rank = 0
            cnt = 0
            rows = DAO.get_toots_hours(hours=hr)
            rows.sort(key=lambda x: (-x[1], x[0]))
            for i, (k, v) in enumerate(rows):
                if k == target:
                    rank = i + 1
                    cnt = v
                    break
            toot_now += f"\n直近１{com}：{cnt:,} toots（{rank}/{len(rows)}位）"

        toot(toot_now, visibility, id, interval=2)

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

        toot(toot_now, visibility='public', spoiler_text=spo_text, interval=2)



def bottlemail_service(content, acct, id, visibility):
# ボトルメールサービス　メッセージ登録
    # fav_now(id)
    word = re.search(r"([ぼボ][とト][るル][メめ]ー[るル])([サさ]ー[ビび][スす])[：:](.*)",
                     str(content), flags=(re.MULTILINE | re.DOTALL)).group(3)
    toot_now = "@" + acct + "\n"
    if len(word) == 0:
        toot(toot_now + "₍₍ ◝(* ,,Ծ‸Ծ,, )◟ ⁾⁾メッセージ入れてー！", visibility , id, None)
        return
    if len(word) > 300:
        toot(toot_now + "₍₍ ◝(* ,,Ծ‸Ծ,, )◟ ⁾⁾長いよー！", visibility , id, None)
        return

    bm = bottlemail.Bottlemail()
    bm.bottling(acct, word, id)

    spoiler = "ボトルメール受け付けたよー！"
    toot_now += "受け付けたメッセージは「" + word + "」だよー！いつか届くから気長に待っててねー！"
    toot(toot_now, visibility, id, spoiler)


def th_worker():
    # ワーカー処理のスレッド
    while True:
        sleep(0.5)
        try:
            status = WorkerQ.get()  # キューからトゥートを取り出すよー！なかったら待機してくれるはずー！
            if WorkerQ.qsize() <= 1:  # キューが詰まってたらスルー
                worker(status)
        except Exception as e:
            logger.error(e, exc_info=True)
            sleep(5)


def th_timerDel():
    # 時限トゥー消し
    while True:
        try:
            status = TimerDelQ.get()  # キューからトゥートを取り出すよー！なかったら待機してくれるはずー！
            id = status["id"]
            acct = status["account"]["acct"]
            hashtags = util.hashtag(status['content'])

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
            logger.error(e, exc_info=True)
            sleep(30)


def jinkei_tooter():
# 陣形
    spoiler = "勝手に陣形サービス"
    gen_txt = romasaga.gen_jinkei()
    if gen_txt:
        toot(gen_txt, "public", spoiler_text=spoiler)


def bottlemail_sending():
# ボトルメールサービス　配信処理
    bm = bottlemail.Bottlemail()
    sendlist = bm.drifting()
    no_bottle_list = set([tmp.strip() for tmp in open(NO_BOTTLE_PATH).readlines(
    ) if os.path.exists(NO_BOTTLE_PATH) and len(tmp.strip()) > 0])

    for id, acct, msg,reply_id in sendlist:

        spoiler = ":@" + acct + ": から🍾ボトルメール💌届いたよー！"
        random_acct = DAO.sample_acct()
        if random_acct in no_bottle_list:
            continue
        #お届け！
        toots = "@" + random_acct + "\n:@" + acct + ": ＜「" + msg + "」"
        toots += "\n※ボトルメールサービス：＜メッセージ＞　であなたも送れるよー！試してみてね！"
        toots += "\n#ボトルメールサービス #きりぼっと"
        toot(toots, "direct", reply_id if reply_id != 0 else None, spoiler)
        bm.sended(id, random_acct)

        #到着通知
        spoiler = ":@" + random_acct + ": が🍾ボトルメール💌受け取ったよー！"
        toots = "@" + acct + " 届けたメッセージは……\n:@" + acct + ": ＜「" + msg + "」"
        toots += "\n#ボトルメールサービス #きりぼっと"
        toot(toots, "direct", reply_id if reply_id != 0 else None, spoiler)


def auto_tooter():
# きりぼっとのつぶやき
    seeds = toots_in_ltl[-20:]
    if len(seeds) <= 2:
        return
    spoiler = None

    gen_txt = dnn_gen_text_wrapper("[SEP]".join([toot for toot, _ in seeds]))
    gen_txt = util.content_cleanser_light(gen_txt)
    if gen_txt[0:1] == '。':
        gen_txt = gen_txt[1:]
    if len(gen_txt) > 60:
        spoiler = f':@{BOT_ID}: 💭'

    toot(gen_txt, "public", None, spoiler)


def th_auto_tooter():
    TT_INT = 1800
    tt_cnt = TT_INT
    pre_toots_len = len(toots_in_ltl)
    while True:
        try:
            sleep(1)
            tt_cnt -= 1
            if len(toots_in_ltl) != pre_toots_len:
                tt_cnt -= random.randint(1,3) * 60
            if len(toots_in_ltl) > 50:
                toots_in_ltl.pop(0)
            pre_toots_len = len(toots_in_ltl)
            if tt_cnt <= 0:
                auto_tooter()
                tt_cnt = TT_INT
        except Exception as e:
            logger.error(e, exc_info=True)


def dnn_gen_text_wrapper(input_text):
    return bert.gen_text(input_text) #, temperature=random.uniform(0.5, 1.0), topk=random.randint(100,500))


def dnn_gen_toot_sub(acct: str, seeds: list, visibility: str, in_reply_to_id: int = None, toots_for_rep:list = None):
    toot_now = f"@{acct}\n"
    tmp = dnn_gen_text_wrapper("[SEP]".join([toot for toot, _ in seeds]))
    tmp = util.content_cleanser_light(tmp)
    if toots_for_rep:
        toots_for_rep[acct].append([tmp, datetime.now(timezone('Asia/Tokyo'))])
    toot_now += tmp
    toot(toot_now, visibility, in_reply_to_id)


def th_delete():
# DELETE時の処理
    del_accts = []
    while True:
        try:
            toot_now = f'@{MASTER_ID} \n'
            row = DAO.pickup_1toot(DelQ.get())
            # 垢消し時は大量のトゥー消しが来るので、キューが溜まってる場合はスキップするよ〜
            if DelQ.qsize() >= 3:
                continue
            logger.info(f'th_delete:{row}')
            if row:
                acct = row[0]
                if acct not in del_accts and acct != BOT_ID:
                    date = f'{row[2]:08d}'
                    time = f'{row[3]:06d}'
                    ymdhms = '%s %s' %(date, time)
                    ymdhms = dateutil.parser.parse(
                        ymdhms).astimezone(timezone('Asia/Tokyo'))
                    toot_now += f':@{row[0]}: 🚓🚓🚓＜う〜う〜！トゥー消し警察でーす！\n'
                    toot_now += f':@{row[0]}: ＜「{util.content_cleanser(row[1])}」 at {ymdhms.strftime("%Y.%m.%d %H:%M:%S")}\n#exp10m'
                    toot(toot_now, 'direct', in_reply_to_id=None,
                            spoiler_text=f':@{row[0]}: がトゥー消ししたよー……', media_ids=None, interval=0)
                    SM.update(row[0], 'func', score=-1)
                    sleep(0.2)

                del_accts.append(acct)
                if len(del_accts) > 3:
                    del_accts.pop(0)

        except Exception as e:
            logger.error(e, exc_info=True)


def th_hint_de_pinto(gtime=5):
    # 初期タイマーセット
    junbiTM = timer.Timer(30*60)
    junbiTM.reset(gtime*60)
    junbiTM.start()
    HintPintoQ.clear()
    while True:
        try:
            tmp_list = HintPintoQ.get(timeout=60)
            g_acct, g_id, term = tmp_list[0], tmp_list[1], tmp_list[2]
            logger.debug(f"ひんぴん開始:{tmp_list}")

            # 準備中確認
            if junbiTM.check() > 0:
                sleep(3)
                remaintm = junbiTM.check()
                toot(f'@{g_acct}\nまだ準備中なのであとで依頼してね〜（準備完了まで{remaintm//60}分{remaintm%60}秒）',
                    'direct', g_id, None)
                sleep(27)
                continue

            # 使用済みワード確認
            hintPinto_words = [tmp.strip() for tmp in open(HINPINED_WORDS_PATH, 'r').readlines(
            ) if os.path.exists(HINPINED_WORDS_PATH) and len(tmp.strip()) > 0]
            if util.normalize_txt(term) in hintPinto_words:
                toot(f'@{g_acct} この前やったお題なので別のにして〜！', 'direct', in_reply_to_id=g_id)
                continue

            # 画像検索
            paths = gi.get_images_forQ(term)
            if len(paths) > 0:
                path = random.choice(paths)
            else:
                toot(f'@{g_acct} 画像が見つからなかったー！', visibility='direct', in_reply_to_id=g_id)
                continue

            # 使用済みワードを追記
            hintPinto_words.append(util.normalize_txt(term))
            if len(hintPinto_words) > 30:
                hintPinto_words.pop(0)
            with open(HINPINED_WORDS_PATH, 'w') as f:
                f.write("\n".join(hintPinto_words))

            event = threading.Event()
            hinpin_sts = dict(hint=False, pinto=False)
            loop_cnt = []
            HintPinto_flg.append('ON')
            HintPinto_ansQ.clear()

            th_hint = threading.Thread(target=hinpin_hint,
                                    args=(event, g_acct, term, path, hinpin_sts, loop_cnt))
            th_hint.start()

            th_pinto = threading.Thread(target=hinpin_pinto,
                                    args=(event, g_acct, term, path, hinpin_sts, loop_cnt))
            th_pinto.start()

            th_hint.join()
            th_pinto.join()

            logger.debug(f"ひんぴんデバッグ:{hinpin_sts}")
            #ゲーム終了後、次回開始までの準備期間
            if 'ON' in HintPinto_flg:
                # 終了後アナウンス
                if hinpin_sts["pinto_info"]["sts"] == "正解":
                    toot(f'((( :@{hinpin_sts["pinto_info"]["a_acct"]}: ))) 正解〜！',
                            visibility='public', in_reply_to_id=None, spoiler_text=None)
                elif  hinpin_sts["pinto_info"]["sts"] == "ばらし":
                    toot(f'[[[ :@{hinpin_sts["pinto_info"]["q_acct"]}: ]]] こら〜！',
                        visibility='public', in_reply_to_id=None, spoiler_text=None)

                sleep(4)
                toot_now = f"正解は{term}でした〜！\n（出題 :@{g_acct}: ） #exp15m"
                ex = path.rsplit('.')[-1]
                if ex == 'jpg':
                    ex = 'jpeg'

                MAX_SIZE = 512
                img = Image.open(path).convert('RGB')
                img = img.resize((img.width*MAX_SIZE//max(img.size),
                                    img.height*MAX_SIZE//max(img.size)), Image.LANCZOS)
                filename = path.split('.')[0] + '_resize.png'
                img.save(filename, "png")
                
                media_files = []
                media_files.append(mastodon.media_post(filename, 'image/' + ex))
                toot(toot_now, visibility='public', in_reply_to_id=None,
                    spoiler_text=None, media_ids=media_files)

                sleep(4)
                if hinpin_sts["pinto_info"]["sts"] == "正解":
                    toot_now  = f'正解者 :@{hinpin_sts["pinto_info"]["a_acct"]}: には{hinpin_sts["pinto_info"]["a_score"]}点、'
                    toot_now += f'出題者 :@{hinpin_sts["pinto_info"]["q_acct"]}: には{hinpin_sts["pinto_info"]["q_score"]}点入るよー！'
                    toot(toot_now, visibility='public', in_reply_to_id=None, spoiler_text=None)
                elif  hinpin_sts["pinto_info"]["sts"] == "ばらし":
                    toot_now = f'出題者 :@{hinpin_sts["pinto_info"]["q_acct"]}: が答えをばらしたので減点{hinpin_sts["pinto_info"]["q_score"]}点だよ〜'
                    toot(toot_now, visibility='public', in_reply_to_id=None, spoiler_text=None)
                elif hinpin_sts["pinto_info"]["sts"] == "正解なし":
                    toot_now =  f'正解者なしのため出題者[[[ :@{hinpin_sts["pinto_info"]["q_acct"]}:]]] にペナルティ〜！' 
                    toot_now += f'\n減点{hinpin_sts["pinto_info"]["q_score"]}点だよ〜'
                    toot(toot_now, visibility='public', in_reply_to_id=None, spoiler_text=None)
                elif hinpin_sts["pinto_info"]["sts"] == "無効":
                    toot_now = f'誰もいなかったので無効試合になったよ〜'
                    toot(toot_now, visibility='public', in_reply_to_id=None, spoiler_text=None)

                HintPinto_flg.remove('ON')
                junbiTM.reset()
                junbiTM.start()

        except queue.Empty:
            logger.debug(f"ひんぴん出題待ちループ:残り{junbiTM.check()}秒")
        except Exception as e:
            logger.error(e, exc_info=True)
            sleep(5)
            toot(f'@{MASTER_ID} ヒントでピントで何かエラー出た！', visibility="public")


def hinpin_hint(event, g_acct, term, path, hinpin_sts, loop_cnt):
    # 出題スレッド
    MAX_SIZE = 512
    img = Image.open(path).convert('RGB')
    img = img.resize((img.width*MAX_SIZE//max(img.size),
                        img.height*MAX_SIZE//max(img.size)), Image.LANCZOS)
    
    mask_map = [i for i in range(len(term))]
    for loop, p in enumerate(range(3, 8, 1)):
        if not hinpin_sts["pinto"]: # 正解者が出ていない
            loop_cnt.append(loop)
            if loop == 0:
                hint_text = "なし"
            elif loop == 1:
                hint_text = "○"*len(term)
            elif loop > 1 and len(mask_map) > 1:
                random.shuffle(mask_map)
                mask_map.pop()
                hint_text = ""
                for i, c in enumerate(term):
                    if i in mask_map:
                        hint_text += "○"
                    else:
                        hint_text += c

            # LANCZOS BICUBIC NEAREST
            re_size = (img.width*(2**p)//max(img.size),
                        img.height*(2**p)//max(img.size))
            tmp = img.resize(re_size, Image.NEAREST)
            tmp = tmp.resize(img.size, Image.NEAREST)
            filename = path.split('.')[0] + f'_{loop}.png'
            tmp.save(filename, "png")
            media_files = []
            media_files.append(
                mastodon.media_post(filename, 'image/png'))
            toot_now = f"さて、これは何/誰でしょうか？\nヒント：{hint_text}\n#きりたんのヒントでピント #exp15m"
            toot(toot_now, visibility='public', in_reply_to_id=None,
                    spoiler_text=None, media_ids=media_files)
            event.set()
            # タイマー
            for _ in range(90):
                sleep(0.5)
                if hinpin_sts["pinto"]: # 正解者が出た場合
                    break
        else:
            break
    # 終了フラグ
    hinpin_sts["hint"] = True
    logger.debug(f"ひんぴんデバッグ:{hinpin_sts}")


def hinpin_pinto(event, g_acct, term, path, hinpin_sts, loop_cnt):
    # 回答スレッド
    event.wait()
    event.clear()
    ans_cnt = 0
    base_score = min([10, len(term)])
    max_score = base_score*16
    logger.debug(f"ひんぴんデバッグ:{hinpin_sts}")
    while True:
        try:
            logger.debug(f"ひんぴんデバッグ:{hinpin_sts}")
            acct, _, ans, vis, *_ = HintPinto_ansQ.get(timeout=0.5)
            ans_cnt += 1
            logger.debug(
                f"ひんぴんデバッグ:acct={acct}  ans={ans}  vis={vis}  cnt={ans_cnt}")
            if g_acct != acct and util.normalize_txt(term) in util.normalize_txt(ans):
                # スコア計算
                a_score = min(
                    int(max_score//(2**(len(loop_cnt) - 1))), max_score)
                q_score = a_score//2 + ans_cnt * 2
                SM.update(acct, 'getnum', score=a_score)
                SM.update(g_acct, 'getnum', score=q_score)
                hinpin_sts["pinto_info"] = dict(sts="正解", a_acct=acct, a_score=a_score, q_acct=g_acct, q_score=q_score)
                break
            elif g_acct == acct and vis != 'direct' and term in ans:
                score = max_score*2
                SM.update(g_acct, 'getnum', score=score*-1)
                hinpin_sts["pinto_info"] = dict(
                    sts="ばらし", a_acct=acct, a_score=0, q_acct=g_acct, q_score=score)
                break
        except queue.Empty:
            # 出題が終わってたら終了
            if hinpin_sts["hint"]: # 出題が終わった場合
                if ans_cnt > 0:
                    score = max_score//4
                    SM.update(g_acct, 'getnum', score=-1*score)
                    hinpin_sts["pinto_info"] = dict(
                        sts="正解なし", a_acct=None, a_score=0, q_acct=g_acct, q_score=score)
                    break
                else:
                    hinpin_sts["pinto_info"] = dict(
                        sts="無効", a_acct=None, a_score=0, q_acct=None, q_score=0)
                    break

    # 終了フラグ
    hinpin_sts["pinto"] = True


def th_gettingnum(gtime=30):
    # 数取りゲーム
    gamenum = 5
    junbiTM = timer.Timer(60*60)
    junbiTM.reset(gtime*60)
    junbiTM.start()
    gameTM = timer.Timer(240)
    while True:
        try:
            g_acct, g_id = GetNumQ.get()
            if junbiTM.check() > 0:
                remaintm = junbiTM.check()
                toot(
                    f'@{g_acct}\n開催準備中だよー！あと{remaintm//60}分{remaintm%60}秒待ってねー！', 'public', g_id, None)
                continue

            #ゲーム開始ー！
            # fav_now(g_id)
            gm = game.GettingNum(gamenum)
            GetNumVoteQ.clear()
            gameTM.reset()
            gameTM.start()
            toot(f'🔸1〜{gamenum}の中から誰とも被らない最大の整数に投票した人が勝ちだよー！\
                    \n🔸きりぼっとにメンション（ＤＭ可）で投票してね！\
                    \n🔸参加者が２人に満たない場合は無効になるよ〜\
                    \n🔸得点は、取った数×参加人数×5点だよ〜\
                    \n🔸制限時間は{int(gameTM.check()/60)}分だよー！はじめ！！\n#数取りゲーム #きりぼっと', 'public', None, '💸数取りゲームＲ３始まるよー！🎮')
            GetNum_flg.append('ON')
            try:
                #残り１分処理
                remaintm = gameTM.check()

                def rm_1m_func():
                    toot(
                        f'数取りゲームＲ３残り１分だよー！(1〜{gamenum})\n※現在の参加人数は{sum(list(map(len,gm.get_results().values() )))}人だよ〜\n#数取りゲーム #きりぼっと', 'public')
                threading.Timer(interval=remaintm - 60,
                                function=rm_1m_func).start()

                while True:
                    remaintm = gameTM.check()
                    if remaintm > 0:
                        #時間切れは例外で抜ける
                        acct, id, num = GetNumVoteQ.get(timeout=remaintm)
                        if gm.vote(acct, num):
                            # fav_now(id)
                            if acct == 'twotwo':
                                toot(f'@{acct}\n{num}だねー！わかったー！',
                                    'direct', id, None)
                        else:
                            toot(f'@{acct}\n٩(๑`^´๑)۶範囲外だよー！',
                                'direct', id, None)
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
            sanka_ninzu = sum(list(map(len, results.values())) )
            if sanka_ninzu <= 1:
                toot('(ง •̀ω•́)ง✧参加者２人未満だったので無効試合になりましたー！\n#数取りゲーム #きりぼっと',
                    'public', None, None)
            else:
                toot_now = ''
                hanamaru = False
                score = 0
                hanaval = 0
                for val, accts in sorted(results.items(), key=lambda x: -x[0]):
                    if len(accts) == 0:
                        continue
                    elif len(accts) == 1 and not hanamaru:
                        toot_now += '💮'
                        hanamaru = True
                        toot_now += f'{val:>2}：'
                        for acct1 in accts:
                            toot_now += f'((( :@{acct1}: )))'
                        toot_now += '\n'
                        score = val * sanka_ninzu * 5
                        hanaval = val
                        SM.update(accts[0], 'getnum', score=score)
                    else:
                        toot_now += '❌'
                        toot_now += f'{val:>2}：'
                        for acct1 in accts:
                            toot_now += f':@{acct1}: '
                        toot_now += '\n'
                if score > 0:
                    toot(f'{toot_now}\n得点は{score}点（取った数:{hanaval}×参加人数:{sanka_ninzu}×5点）だよー\n#数取りゲーム #きりぼっと',
                            'public', None, '数取りゲーム、結果発表ーー！！')
                else:
                    toot(f'{toot_now}\n勝者はいなかったよ〜😢\n#数取りゲーム #きりぼっと',
                            'public', None, '数取りゲーム、結果発表ーー！！')

        except Exception as e:
            logger.error(e, exc_info=True)


def th_saver():
# トゥートをいろいろ
    while True:
        status = StatusQ.get()
        # 業務連絡
        business_contact(status)
        # トゥートを保存
        try:
            DAO.save_toot(status)
        except Exception as e:
            #保存失敗したら、キューに詰めてリトライ！
            logger.error(e, exc_info=True)
            sleep(10)
            # StatusQ.put(status)


def wan_time():
# わんタイム
    gen_txt = 'わんわんわんわん！\n₍₍ （（（｛｛｛ฅ(  ᐡ ˘ܫ˘ ᐡ )ฅ｝｝｝））） ⁾⁾ ₍₍（（（｛｛｛ฅ( ᐡ╹ܫ╹ᐡ ฅ)｝｝｝）））⁾⁾'
    toot(gen_txt, "public")


def nyan_time():
# にゃんタイム
    gen_txt = 'にゃんにゃんにゃんにゃん！\n₍₍（（（｛｛｛(ฅ=˘꒳ ˘=)ฅ｝｝｝））） ⁾⁾ ₍₍ （（（｛｛｛ฅ(=╹꒳ ╹=ฅ)｝｝｝）））⁾⁾'
    toot(gen_txt, "public")


def jihou():
# 時報
    jst_now = datetime.now(timezone('Asia/Tokyo'))
    hh_now = jst_now.strftime("%H")
    toot(f"((({jihou_dict[hh_now]})))ぽっぽ〜", "public")


def th_post():
# post用worker
    interval_time = 0
    while True:
        logger.debug(f"interval_time={interval_time}")
        sleep(max(0.2, min(interval_time, 4)))
        try:
            func, args, kwargs = PostQ.get(timeout=2)
            func(*args, **kwargs)
            interval_time += 0.4
        except queue.Empty:
            interval_time -= 0.2
            if interval_time < 0:
                interval_time = 0
        except Exception as e:
            logger.error(e, exc_info=True)
            sleep(3)


def th_ltl():
    # ltl監視
    while True:
        try:
            mastodon.stream_local(ltl_listener())
        except Exception as e:
            logger.error(e, exc_info=True)
            sleep(10)


def th_ptl():
    # ltl監視
    while True:
        try:
            publicdon.stream_local(public_listener())
        except Exception as e:
            logger.error(e, exc_info=True)
            sleep(10)


def th_htl():
    # ltl監視
    while True:
        try:
            mastodon.stream_user(notification_listener())
        except Exception as e:
            logger.error(e, exc_info=True)
            sleep(10)


def run():
    args = get_args()
    threads = []
    CM.run()
    #タイムライン受信系
    threads.append(threading.Thread(target=th_ltl))
    threads.append(threading.Thread(target=th_ptl))
    threads.append(threading.Thread(target=th_htl))
    # mastodon.stream_local(ltl_listener(), run_async=True)
    # publicdon.stream_local(public_listener(), run_async=True)
    # mastodon.stream_user(notification_listener(), run_async=True)
    #タイムライン応答系
    threads.append(threading.Thread(target=th_delete))
    threads.append(threading.Thread(target=th_saver))
    threads.append(threading.Thread(target=th_gettingnum, args=(args.gtime,)))
    threads.append(threading.Thread(target=th_hint_de_pinto, args=(args.htime,)))
    threads.append(threading.Thread(target=th_worker))
    threads.append(threading.Thread(target=th_timerDel))
    threads.append(threading.Thread(target=th_post))
    threads.append(threading.Thread(target=th_auto_tooter))
    #スケジュール起動系(時刻)
    threads.append(scheduler.Scheduler(
        bottlemail_sending, hhmm_list=['23:05']))
    threads.append(scheduler.Scheduler(wan_time, hhmm_list=['11:11']))
    threads.append(scheduler.Scheduler(nyan_time, hhmm_list=['22:22']))
    threads.append(scheduler.Scheduler(show_rank, hhmm_list=['07:00']))
    threads.append(scheduler.Scheduler(jihou, hhmm_list=['**:00']))

    #スケジュール起動系(間隔)
    threads.append(scheduler.Scheduler(
        jinkei_tooter, hhmm_list=None, intvl=120, rndmin=-10, rndmax=10, cm=CM))

    for th in threads:
        th.start()


if __name__ == '__main__':
    toots = DAO.get_user_toots('5M')
    for tid, tcontent, tdate, ttime in toots:
        status = mastodon.status(tid)
        print(status)
