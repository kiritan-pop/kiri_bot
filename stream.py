# -*- coding: utf-8 -*-

from mastodon import Mastodon,StreamListener
import re, os, json, random, unicodedata, signal, sys
import threading, MeCab, queue, urllib
import concurrent.futures
from time import sleep
from pytz import timezone
import dateutil
from datetime import datetime,timedelta
import warnings, traceback
from bs4 import BeautifulSoup
from os.path import join, dirname
from dotenv import load_dotenv
import Toot_summary, GenerateText, PrepareChain, bottlemail  #自前のやつー！
import kiri_util, kiri_deep, kiri_game  #自前のやつー！

BOT_ID = 'kiri_bot01'
BOTS = [BOT_ID,'JC','12222222','friends_booster']
DELAY = 2
pat1 = re.compile(r' ([!-~ぁ-んァ-ン] )+|^([!-~ぁ-んァ-ン] )+| [!-~ぁ-んァ-ン]$',flags=re.MULTILINE)  #[!-~0-9a-zA-Zぁ-んァ-ン０-９ａ-ｚ]
pat2 = re.compile(r'[ｗ！？!\?]')
#NGワード
ng_words = set(word.strip() for word in open('.ng_words').readlines())

#停止用
STOPPA = []

#得点管理、流速監視
SM = kiri_util.ScoreManager()
CM = kiri_util.CoolingManager(10)

#.envファイルからトークンとかURLを取得ー！
dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)
MASTODON_URL = os.environ.get("MASTODON_URL")
MASTODON_ACCESS_TOKEN = os.environ.get("MASTODON_ACCESS_TOKEN")

mastodon = Mastodon(
    access_token=MASTODON_ACCESS_TOKEN,
    api_base_url=MASTODON_URL)  # インスタンス

TQ = queue.Queue()
StatusQ = queue.Queue()
Toot1bQ = queue.Queue()
DelQ = queue.Queue()
GetNumQ = queue.Queue()
GetNumVoteQ = queue.Queue()

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
hanalist.append('🌷🌸🌹🌺🌻🌼大当たり！🌼🌻🌺🌹🌸🌷  @kiritan')

#######################################################
# マストドンＡＰＩ用部品を継承して、通知時の処理を実装ー！
class men_toot(StreamListener):
    def on_notification(self, notification):
        print("===通知===")
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        ymdhms = jst_now.strftime("%Y%m%d %H%M%S")

        if notification["type"] == "mention":
            status = notification["status"]
            vote_check(status)
            quick_rtn(status)
            TQ.put(status)
            StatusQ.put(status)
            SM.update(notification["status"]["account"]["acct"], 'reply')
        elif notification["type"] == "favourite":
            SM.update(notification["account"]["acct"], 'fav', ymdhms)
        elif notification["type"] == "reblog":
            SM.update(notification["account"]["acct"], 'boost', ymdhms)

#######################################################
# マストドンＡＰＩ用部品を継承して、ローカルタイムライン受信時の処理を実装ー！
class res_toot(StreamListener):
    def on_update(self, status):
        #print("===ローカルタイムライン===")
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
            StatusQ.put(status)
            #bot達のLTLトゥートは無視する(ง •̀ω•́)ง✧＜無限ループ防止！
            if  status["account"]["username"] in BOTS:
                return
            TQ.put(status)
            quick_rtn(status)
            CM.count(status['created_at'])

    def on_delete(self, status_id):
        print(str("===削除されました【{}】===").format(str(status_id)))
        DelQ.put(status_id)

#######################################################
# トゥート処理
def toot(toot_now, g_vis, rep=None, spo=None, media_ids=None, interval=0):
    def th_toot(toot_now, g_vis, rep, spo, media_ids):
        mastodon.status_post(status=toot_now[0:450], visibility=g_vis, in_reply_to_id=rep, spoiler_text=spo, media_ids=media_ids)
    th = threading.Timer(interval,th_toot,args=(toot_now, g_vis, rep, spo, media_ids))
    th.start()
    print("🆕toot:" + toot_now[0:50] + ":" + g_vis )

#######################################################
# ファボ処理
def fav_now(id):  # ニコります
    status = mastodon.status(id)
    if status['favourited'] == False:
        mastodon.status_favourite(id)
        print("🙆Fav")

#######################################################
# ブースト
def boost_now(id):  # ぶーすと！
    status = mastodon.status(id)
    if status['reblogged'] == False:
        mastodon.status_reblog(id)
    else:
        mastodon.status_unreblog(id)
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
# エラー時のログ書き込み
def error_log():
    jst_now = datetime.now(timezone('Asia/Tokyo'))
    ymdhms = jst_now.strftime("%Y/%m/%d %H:%M:%S")
    with open('error.log', 'a') as f:
        f.write('\n####%s####\n'%ymdhms)
        traceback.print_exc(file=f)
    print("###%s 例外情報\n"%ymdhms + traceback.format_exc())

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

    for ng_word in ng_words:
        if ng_word in tmp.text:
            return ""

    rtext = ''
    ps = []
    for p in tmp.find_all("p"):
        ps.append(p.text)
    rtext += '。\n'.join(ps)
    rtext = unicodedata.normalize("NFKC", rtext)
    rtext = re.sub(r'([^:])@', r'\1', rtext)
    rtext = rtext.replace("#","")
    rtext = re.sub(r'(___R___)\1{2,}', r'\1', rtext)
    #rtext = re.sub(r'([^。|^？|^！|^\?|^!])___R___', r'\1。\n', rtext)
    rtext = re.sub(r'___R___', r'\n', rtext)
    if hashtag != "":
        return rtext + " #" + hashtag
    else:
        return rtext

#######################################################
# 数取りゲーム 投票前処理
def vote_check(status):
    acct = status["account"]["acct"]
    id = status["id"]
    if re.search(r'[^:]@kiri_bot01', status['content']):
        content = content_cleanser(status['content'])
        if len(content) == 0:
            return
        if acct == 'twotwo' and re.search(r'!', content):
            twocnt = content.count('トゥ')
            GetNumVoteQ.put([acct, id, int(101 - twocnt)])
        else:
            if content.strip().isdigit():
                GetNumVoteQ.put([acct,id,int(content.strip())])

#######################################################
# 即時応答処理ー！
def quick_rtn(status):
    id = status["id"]
    acct = status["account"]["acct"]
    username = "@" +  acct
    g_vis = status["visibility"]
    content = content_cleanser(status['content'])
    statuses_count = status["account"]["statuses_count"]
    spoiler_text = status["spoiler_text"]

    if len(content) <= 0:
        return

    if  Toot1bQ.empty():
        content_1b, acct_1b, id_1b, g_vis_1b = None,None,None,None
    else:
        content_1b, acct_1b, id_1b, g_vis_1b = Toot1bQ.get() #キューから１回前を取得
    #
    Toot1bQ.put((content, acct, id, g_vis))

    if re.search(r"(緊急|強制)(再起動)", content) and acct == 'kiritan':
        print("＊＊＊＊＊＊＊＊＊＊＊再起動するよー！＊＊＊＊＊＊＊＊＊＊＊")
        toot("@kiritan 再起動のため一旦終了しまーす！", 'direct', id ,None)
        sleep(10)
        os.kill(os.getpid(), signal.SIGKILL)
    if re.search(r"(緊急|強制)(停止|終了)", content) and acct == 'kiritan':
        print("＊＊＊＊＊＊＊＊＊＊＊緊急停止したよー！＊＊＊＊＊＊＊＊＊＊＊")
        toot("@kiritan 緊急停止しまーす！", 'direct', id ,None)
        sleep(10)
        STOPPA.append('stop')
        sys.exit()
    try:
        a = int(CM.get_coolingtime())
        rnd = random.randint(-1,7+a)
        if rnd == -1:
            return
        toot_now = ''
        id_now = id
        vis_now = g_vis
        interval = 0
        if statuses_count != 3 and  (statuses_count - 3)%10000 == 0:
            interval = 3
            toot_now = username + "\n"
            toot_now += "あ！そういえばさっき{0:,}トゥートだったよー！".format(statuses_count-3)
            vis_now = 'unlisted'
            SM.update(acct, 'func')
        elif statuses_count == 1:
            interval = 5
            toot_now = username + "\n"
            toot_now += "新規さんいらっしゃーい！🍵🍡どうぞー！"
            vis_now = 'unlisted'
            SM.update(acct, 'func')
        elif re.search(r"草", content+spoiler_text):
            SM.update(acct, 'func',score=-1)
            if rnd <= 1:
                toot_now = ":" + username + ": " + username + " "
                random.shuffle(hanalist)
                toot_now += hanalist[0]
        elif re.search(r"^:twitter:.+🔥$", content, flags=(re.MULTILINE | re.DOTALL)):
            SM.update(acct, 'func')
            if rnd <= 3:
                toot_now = ":" + username + ": " + username + " "
                toot_now += '\n:twitter: ＜ﾊﾟﾀﾊﾟﾀｰ\n川\n\n🔥'
                vis_now = 'direct'
            elif rnd <= 6:
                toot_now = ":" + username + ": " + username + " "
                toot_now += '\n(ﾉ・_・)ﾉ ﾆｹﾞﾃ!⌒:twitter: ＜ｱﾘｶﾞﾄｩ!\n🔥'
                vis_now = 'direct'
            elif rnd <= 7:
                toot_now = ":" + username + ": " + username + " "
                toot_now += '\n(ﾉ・_・)ﾉ ﾆｹﾞﾃ!⌒🍗 ＜ｱﾘｶﾞﾄｩ!\n🔥'
                vis_now = 'direct'
        elif re.search(r"ブリブリ|ぶりぶり|うん[ちこ]|💩|^流して$", content+spoiler_text):
            SM.update(acct, 'func',score=-1)
            if rnd <= 3:
                toot_now = '🌊🌊🌊 ＜ざばーっ！'
                vis_now = 'public'
                id_now = None
        elif re.search(r"^ふきふき$", content):
            SM.update(acct, 'func')
            if rnd <= 3:
                toot_now = '💨💨💨🍃＜ふわ〜っ！'
                vis_now = 'public'
                id_now = None
        elif re.search(r"^ぬるぽ$", content):
            SM.update(acct, 'func',score=-1)
            if rnd <= 6:
                toot_now = 'ｷﾘｯ'
                vis_now = 'public'
                id_now = None
        elif re.search(r"^通過$", content):
            toot_now = '%s ⊂(｀・ω・´)⊃＜阻止！'%username
            vis_now = 'direct'
            SM.update(acct, 'func')
            if rnd <= 4:
                toot_now = '⊂(｀・ω・´)⊃＜阻止！'
                vis_now = 'public'
                id_now = None
        elif re.search(r"3.{0,1}3.{0,1}4", content):
            toot_now = '%s ﾅﾝ'%username
            vis_now = 'direct'
            SM.update(acct, 'func')
            if rnd <= 6:
                toot_now = 'ﾅﾝ'
                vis_now = 'public'
                id_now = None
        elif re.search(r"^ちくわ大明神$", content):
            toot_now = '%s ﾀﾞｯ'%username
            vis_now = 'direct'
            SM.update(acct, 'func',score=-1)
            if rnd <= 6:
                toot_now = 'ﾀﾞｯ'
                vis_now = 'public'
                id_now = None
        elif re.search(r"ボロン$|ぼろん$", content):
            SM.update(acct, 'func',score=-1)
            if rnd <= 3:
                toot_now = '@%s\n✂️チョキン！！'%acct
                vis_now = 'direct'
        elif re.search(r"さむい$|寒い$", content):
            SM.update(acct, 'func',score=-1)
            if rnd <= 3:
                toot_now = '@%s\n🔥🔥🔥\n🔥:@%s:🔥\n🔥🔥🔥 '%(acct,acct)
                vis_now = 'direct'
        elif re.search(r"あつい$|暑い$", content):
            SM.update(acct, 'func',score=-1)
            if rnd <= 3:
                toot_now = '@%s\n❄❄❄\n❄:@%s:❄\n❄❄❄ '%(acct,acct)
                vis_now = 'direct'
        elif re.search(r"^(今|いま)の[な|無|ナ][し|シ]$", content):
            toot_now = '%s :%s:🚓🚓🚓＜う〜う〜！いまのなし警察でーす！'%(username, username)
            vis_now = 'direct'
            SM.update(acct, 'func',score=-1)
            if rnd <= 3:
                toot_now = '🚓🚓🚓＜う〜う〜！いまのなし警察でーす！'
                vis_now = 'public'
                id_now = None
        elif re.search(r"ツイッター|ツイート|[tT]witter", content):
            SM.update(acct, 'func',score=-1)
            if rnd <= 3:
                toot_now = '@%s\nつ、つつつ、つい〜〜！！？！？？！？！'%acct
                vis_now = 'direct'
            elif rnd == 6:
                toot_now = '@%s\nつい〜……'%acct
                vis_now = 'direct'
        elif re.search(r"(:nicoru[0-9]{0,3}:.?){4}", content):
            if content_1b != None and acct == acct_1b:
                if re.search(r"(:nicoru[0-9]{0,3}:.?){3}", content_1b):
                    SM.update(acct, 'func')
                    toot_now = '%s　　三(  っ˃̵ᴗ˂̵) 通りまーす！'%username
                    vis_now = 'direct'
                    SM.update(acct, 'func')
                    if rnd <= 4:
                        toot_now = '　　三(  っ˃̵ᴗ˂̵) 通りまーす！'
                        vis_now = 'public'
                        id_now = None
        elif re.search(r"(:nicoru[0-9]{0,3}:.?){2}", content):
            if content_1b != None and acct == acct_1b:
                SM.update(acct, 'func')
                if re.search(r"(:nicoru[0-9]{0,3}:.?){3}", content_1b):
                    toot_now = '%s　　(˃̵ᴗ˂̵っ )三 通りまーす！'%username
                    vis_now = 'direct'
                    SM.update(acct, 'func')
                    if rnd <= 4:
                        toot_now = '　　(˃̵ᴗ˂̵っ )三 通りまーす！'
                        vis_now = 'public'
                        id_now = None
        elif re.search(r"^貞$", content):
            if content_1b != None and acct == acct_1b:
                SM.update(acct, 'func',score=-1)
                if re.search(r"^治$", content_1b):
                    toot_now = '%s　　三(  っ˃̵ᴗ˂̵) 通りまーす！'%username
                    vis_now = 'direct'
                    SM.update(acct, 'func')
                    if rnd <= 7:
                        toot_now = '　　三(  っ˃̵ᴗ˂̵) 通りまーす！'
                        vis_now = 'public'
                        id_now = None
        elif "*´ω｀*" in content+spoiler_text:
            SM.update(acct, 'func',score=-1)
            if rnd <= 6:
                toot_now = '@%s\nその顔は……！！'%acct
                vis_now = 'direct'
        elif "きりちゃん" in content+spoiler_text or "ニコって" in content+spoiler_text:
            fav_now(id)
            SM.update(acct, 'reply')
        elif re.search(r"なんでも|何でも",content):
            SM.update(acct, 'func',score=-1)
            if rnd <= 4:
                toot_now = '@%s\nん？'%acct
                vis_now = 'direct'
        elif re.search(r"泣いてる|泣いた|涙が出[るた(そう)]", content):
            SM.update(acct, 'func')
            if rnd <= 4:
                toot_now = '@%s\n泣いてるー！ｷｬｯｷｬｯ!'%acct
                vis_now = 'direct'
        elif re.search(r"惚気|ほっけ|ホッケ|^燃やして$", content+spoiler_text):
            SM.update(acct, 'func',score=-1)
            if rnd <= 4:
                toot_now = '🔥🔥🔥🔥＜ごぉぉぉっ！'
                vis_now = 'public'
                id_now = None
        elif re.search(r"[ご御夕昼朝][食飯][食た]べ[よるた]|(腹|はら)[へ減]った|お(腹|なか)[空す]いた|(何|なに)[食た]べよ", content):
            SM.update(acct, 'func')
            if rnd <= 3:
                recipe_service(content=content, acct=acct, id=id, g_vis=g_vis)
        else:
            return
        #
        if len(toot_now) > 0:
            toot(toot_now, vis_now, id_now, None, None, interval)

    except:
        error_log()

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
def recipe_service(content=None, acct='kiritan', id=None, g_vis='unlisted'):
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
    if not os.path.exists("db/users_size_today.json") :
        return

    fav_now(id)
    dt = datetime.fromtimestamp(os.stat("db/users_size_today.json").st_mtime)
    today_str = dt.strftime('%Y/%m/%d')
    users_size = {}
    users_size_today = {}
    users_cnt = {}
    users_cnt_today = {}
    rank_ruikei = {}
    rank_ruikei_rev = {}
    rank_today = {}
    rank_today_rev = {}
    with open("db/users_size.json", 'r') as f:
        users_size = json.load(f)
    with open("db/users_size_today.json", 'r') as f:
        users_size_today = json.load(f)
    with open("db/users_cnt.json", 'r') as f:
        users_cnt = json.load(f)
    with open("db/users_cnt_today.json", 'r') as f:
        users_cnt_today = json.load(f)

    #print(users_size)
    for i,(k, size) in enumerate(sorted(users_size.items(), key=lambda x: -x[1])):
        rank_ruikei[k] = i+1
        rank_ruikei_rev[i+1] = k
    for i,(k, size) in enumerate(sorted(users_size_today.items(), key=lambda x: -x[1])):
        rank_today[k] = i+1
        rank_today_rev[i+1] = k

    if acct not in users_size_today:
        toot('@%s …ランク外だよー！どんまい！'%acct, g_vis ,id, None)
        return

    spoiler = ":@{0}: のランクだよー！（※{1} 時点）".format(acct,today_str)
    toot_now = "@{0} :@{1}: のランクは……\n".format(acct,acct)
    toot_now += "{0:>3}位 {1:,}字/avg{2:.1f}\n".format(rank_today[acct], users_size_today[acct], users_size_today[acct]/users_cnt_today[acct])
    toot_now += "（累計 {0:>3}位 {1:,}字/avg{2:.1f}）\n\n".format(rank_ruikei[acct], users_size[acct], users_size[acct]/users_cnt[acct])
    toot_now += "前後のランクの人は……\n"

    #１ランク上の人ー！
    if rank_today[acct] > 1:
        acct_1b =  rank_today_rev[rank_today[acct] -1 ]
        toot_now += "　:@{3}: {0:>3}位 {1:,}字/avg{2:.1f}\n".format(rank_today[acct_1b], users_size_today[acct_1b], users_size_today[acct_1b]/users_cnt_today[acct_1b], acct_1b)
        toot_now += "（累計 {0:>3}位 {1:,}字/avg{2:.1f}）\n\n".format(rank_ruikei[acct_1b], users_size[acct_1b], users_size[acct_1b]/users_cnt[acct_1b])

    #１ランク下の人ー！
    if rank_today[acct] < len(rank_today):
        acct_1b =  rank_today_rev[rank_today[acct] +1 ]
        toot_now += "　:@{3}: {0:>3}位 {1:,}字/avg{2:.1f}\n".format(rank_today[acct_1b], users_size_today[acct_1b], users_size_today[acct_1b]/users_cnt_today[acct_1b], acct_1b)
        toot_now += "（累計 {0:>3}位 {1:,}字/avg{2:.1f}）\n\n".format(rank_ruikei[acct_1b], users_size[acct_1b], users_size[acct_1b]/users_cnt[acct_1b])

    toot(toot_now, g_vis ,id, spoiler)

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
    while len(STOPPA)==0:
        status = TQ.get() #キューからトゥートを取り出すよー！なかったら待機してくれるはずー！
        id = status["id"]
        acct = status["account"]["acct"]
        g_vis = status["visibility"]
        content = content_cleanser(status['content'])
        spoiler_text = content_cleanser(status["spoiler_text"])
        media_attachments = status["media_attachments"]
        sensitive = status['sensitive']
        print('=== %s  by %s'%('\n    '.join(content.split('\n')), acct))
        try:
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
            elif re.search(r"(私|わたし|わたくし|自分|僕|俺|朕|ちん|余|あたし|ミー|あちき|あちし|\
                わい|わっち|おいどん|わし|うち|おら|儂|おいら|あだす|某|麿|拙者|小生|あっし|手前|吾輩|我輩|マイ)の(ランク|ランキング|順位)", content):
                toot('@%s このサービスは終了したよ〜(৹ᵒ̴̶̷᷄﹏ᵒ̴̶̷᷅৹)'%acct, g_vis, id, None,interval=3)
                #show_rank(acct=acct, id=id, g_vis=g_vis)
                SM.update(acct, 'func')
            elif re.search(r"(数取りゲーム).*(おねがい|お願い)", content):
                print('数取りゲーム受信')
                GetNumQ.put([acct,id])
                SM.update(acct, 'func')
            elif  '?トゥトゥトゥ' in content and acct == 'twotwo': #ネイティオ専用
                GetNumQ.put([acct,id])
                SM.update(acct, 'func')
            elif len(media_attachments) > 0:
                toot_now = ''
                a = int(CM.get_coolingtime())
                if random.randint(0,10+a) <= 7:
                    continue
                for media in media_attachments:
                    filename = download(media["url"] , "media")
                    if '.mp' in filename or '.webm' in filename:
                        continue
                    result = kiri_deep.takoramen(filename)
                    print('   ',result)
                    if result == 'cat':
                        toot_now += 'にゃーん'
                    elif result == 'darts':
                        toot_now += '🎯ダーツ！'
                    elif result == 'nijie_ero':
                        toot_now += 'えっち！'
                    elif result == 'nijie_hiero':
                        toot_now += 'かわいい！'
                    elif result == 'robisute':
                        toot_now += '🙏ろびすてとうとい！'
                    elif sensitive:
                        if result == 'takoyaki':
                            toot_now += 'たこ焼き！'
                        elif result == 'ramen':
                            toot_now += '🍜ちゅるちゅるーっ！'
                        elif result == 'omurice':
                            toot_now += 'オムライス！'
                        elif result == 'sushi':
                            toot_now += 'おすし！'
                        elif result == 'yakiniku':
                            toot_now += '焼き肉！'
                        elif result == 'carry':
                            toot_now += '🍛ごくごくー！'
                        elif result == 'hamburg':
                            toot_now += 'さわやかだなー！'
                        elif result == 'hamburger':
                            toot_now += '🍔もぐもぐー！'
                        elif result == 'karaage':
                            toot_now += 'かけるよね？っ🍋'
                        elif result == 'salada':
                            toot_now += '🥗さくさくー！'
                        elif result == 'sweet':
                            toot_now += '🍧 🍨 🍦 🍰 🎂 🍮 🍩 あまーい！'
                        elif result == 'chahan':
                            toot_now += '焦がしにんにくのマー油と葱油が香るザ★チャーハン600g！？！？！？'
                        elif result == 'yakitori':
                            toot_now += '鳥貴族ーー！！！！'
                        elif result == 'pizza':
                            toot_now += 'ぽざ！'
                    else:
                        if result == 'takoyaki':
                            toot_now += ':@%s: 🚓🚓🚓＜う〜う〜！飯テロ警察 たこ焼き%d課でーす！'%(acct,random.randint(1,5))
                            break
                        elif result == 'ramen':
                            toot_now += ':@%s: 🚓🚓🚓＜う〜う〜！飯テロ警察 ラーメン%d課でーす！'%(acct,random.randint(1,5))
                            break
                        elif result == 'omurice':
                            toot_now += ':@%s: 🚓🚓🚓＜う〜う〜！飯テロ警察 オムライス%d課でーす！'%(acct,random.randint(1,5))
                            break
                        elif result == 'sushi':
                            toot_now += ':@%s: 🚓🚓🚓＜う〜う〜！飯テロ警察 お寿司%d課でーす！'%(acct,random.randint(1,5))
                            break
                        elif result == 'yakiniku':
                            toot_now += ':@%s: 🚓🚓🚓＜う〜う〜！飯テロ警察 焼き肉%d課でーす！'%(acct,random.randint(1,5))
                            break
                        elif result == 'carry':
                            toot_now += ':@%s: 🚓🚓🚓＜う〜う〜！飯テロ警察 カレーライス%d課でーす！'%(acct,random.randint(1,5))
                        elif result == 'hamburg':
                            toot_now += ':@%s: 🚓🚓🚓＜う〜う〜！飯テロ静岡県警でーす！'%acct
                        elif result == 'hamburger':
                            toot_now += ':@%s: 🚓🚓🚓＜う〜う〜！飯テロ警察 マクナル%d課でーす！'%(acct,random.randint(1,5))
                        elif result == 'karaage':
                            toot_now += ':@%s: 🚓🚓🚓＜う〜う〜！飯テロ警察 唐揚げ%d課でーす！'%(acct,random.randint(1,5))
                        elif result == 'salada':
                            toot_now += ':@%s: 🚓🚓🚓＜う〜う〜！飯テロ警察 野菜%d課でーす！'%(acct,random.randint(1,5))
                        elif result == 'sweet':
                            toot_now += ':@%s: 🚓🚓🚓＜う〜う〜！飯テロ警察 甘味%d課でーす！'%(acct,random.randint(1,5))
                        elif result == 'chahan':
                            toot_now += ':@%s: 🚓🚓🚓＜う〜う〜！飯テロ警察 チャーハン%d課でーす！'%(acct,random.randint(1,5))
                        elif result == 'yakitori':
                            toot_now += ':@%s: 🚓🚓🚓＜う〜う〜！飯テロ警察 焼き鳥%d課でーす！'%(acct,random.randint(1,5))
                        elif result == 'pizza':
                            toot_now += ':@%s: 🚓🚓🚓＜う〜う〜！飯テロ警察 ピザ%d課でーす！'%(acct,random.randint(1,5))

                if len(toot_now) > 0:
                    toot_now = "@%s\n"%acct + toot_now
                    fav_now(id)
                    sleep(DELAY)
                    toot(toot_now, g_vis, id, None,interval=8)
            elif len(content) > 140:
                content = re.sub(r"(.)\1{3,}",r"\1",content, flags=(re.DOTALL))
                gen_txt = Toot_summary.summarize(pat1.sub("",pat2.sub("",content)),limit=10,lmtpcs=1, m=1, f=4)
                if gen_txt[-1:1] == '#':
                    gen_txt = gen_txt[:len(gen_txt)-1]
                print('★要約結果：',gen_txt)
                if is_japanese(gen_txt):
                    if len(gen_txt) > 5:
                        gen_txt +=  "\n#きり要約 #きりぼっと"
                        toot("@" + acct + " :@" + acct + ":\n"  + gen_txt, g_vis, id, "勝手に要約サービス")
            elif re.search(r"(きり|キリ).*(ぼっと|ボット|[bB][oO][tT])", content + spoiler_text):
                fav_now(id)
                toot_now = "@%s\n"%acct
                toot_now += kiri_deep.gentxt(content)
                toot(toot_now, g_vis, id, None)
            else:
                continue

            stm = CM.get_coolingtime()
            print('worker sleep :%fs'%stm )
            sleep(stm)

        except:
            error_log()

#######################################################
# スケジューラー！
def th_kiri_scheduler(func,mms=None,intvl=60,rndmin=0,rndmax=0):
    #func:起動する処理
    #mm:起動時刻（分）
    #intmm:起動間隔（分）
    while len(STOPPA)==0:
        sleep(15)
        if rndmin == 0 and rndmax == 0 or rndmin >= rndmax:
            rndmm = 0
        else:
            rndmm = random.randint(rndmin,rndmax)

        cmm = int(CM.get_coolingtime())
        #時刻指定がなければ、インターバル分＋流速考慮値
        if mms == None:
            a = (intvl+cmm+rndmm)*60
            print('###%s###  start at : %ds'%(func,a))
            sleep(a)
            func()
            continue

        #以降は時刻指定時の処理
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        mm = jst_now.strftime("%M")
        #print('###%s###  start at: **:%s'%(func,mms))
        if mm in mms:
            func()
            sleep(60)


#######################################################
# 定期ものまねさーびす！
def monomane_tooter():
    DAO = kiri_util.DAO_statuses()
    spoiler = "勝手にものまねサービス"
    random_acct = DAO.sample_acct(timedelta(minutes=15))
    toots = ""
    for row in DAO.get_user_toots(random_acct):
        content = content_cleanser(row[0])
        if len(content) == 0:
            pass
        else:
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
    DAO = kiri_util.DAO_statuses()
    spoiler = "ＬＴＬここ1時間の自動まとめ"
    toots = ""
    for row in DAO.get_toots_1hour():
        content = content_cleanser(row[0])
        if len(content) == 0:
            pass
        else:
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
    DAO = kiri_util.DAO_statuses()
    bm = bottlemail.Bottlemail()
    sendlist = bm.drifting()
    for id,acct,msg,reply_id in sendlist:
        sleep(DELAY)
        spoiler = ":@" + acct + ": から🍾ボトルメール💌届いたよー！"
        random_acct = DAO.sample_acct(timedelta(hours=1))
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
    DAO = kiri_util.DAO_statuses()
    random_acct = DAO.sample_acct(timedelta(minutes=15))
    boost_now(DAO.get_random_1id(random_acct))
    SM.update(random_acct, 'func')

#######################################################
# きりぼっとのつぶやき
def lstm_tooter():
    DAO = kiri_util.DAO_statuses()
    seeds = DAO.get_least_10toots()
    if len(seeds) <= 2:
        return
    seedtxt = "".join(seeds)
    spoiler = None
    gen_txt = kiri_deep.gentxt(seedtxt)
    if gen_txt[0:1] == '。':
        gen_txt = gen_txt[1:]
    if len(gen_txt) > 40:
        spoiler = ':@%s: 💭'%BOT_ID

    toot(gen_txt, "public", None, spoiler)

#######################################################
# DELETE時の処理
def th_delete():
    DAO = kiri_util.DAO_statuses()
    acct_1b = ''
    while len(STOPPA)==0:
        try:
            toot_now = '@kiritan \n'
            row = DAO.pickup_1toot(DelQ.get())
            print('th_delete:',row)
            if row:
                if acct_1b != row[0]:
                    toot_now += ':@%s: 🚓🚓🚓＜う〜う〜！トゥー消し警察でーす！\n'%row[0]
                    toot_now += ':@%s: ＜「%s」'%( row[0], content_cleanser(row[1]) )
                    toot(toot_now, 'direct', rep=None, spo=':@%s: がトゥー消ししたよー……'%row[0], media_ids=None, interval=0)
                    #print('**DELETE:',row[0],row[1])
                    acct_1b = row[0]
                    SM.update(row[0], 'func', score=-1)
        except:
            error_log()

#######################################################
# 数取りゲーム
def th_gettingnum():
    DAO = kiri_util.DAO_statuses()
    gamenum = 100
    junbiTM = kiri_util.KiriTimer(3600)
    junbiTM.reset(0)
    gameTM = kiri_util.KiriTimer(240)
    while len(STOPPA)==0:
        g_acct,g_id = GetNumQ.get()
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
        except:
            pass
        #ゲーム終了後、次回開始までの準備期間
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

#######################################################
# はーとびーと！
def th_haertbeat():
    while True:
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        ymdhms = jst_now.strftime("%Y/%m/%d %H:%M:%S")
        with open('.heartbeat', 'w') as f:
            f.write(ymdhms)
#######################################################
# トゥートを保存する
def th_status_saver():
    DAO = kiri_util.DAO_statuses()
    while True:
        status = StatusQ.get()
        # トゥートを保存
        try:
            DAO.save_toot(status)
        except:
            #保存失敗したら、キューに詰めてリトライ！
            StatusQ.put(status)
            error_log()
            sleep(30)

#######################################################
# メイン
def main():
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:
        #タイムライン受信系
        #ex.submit(mastodon.stream_local, res_toot() ) #LTL
        ex.submit(mastodon.stream_public, res_toot() ) #FTL
        ex.submit(mastodon.stream_user,   men_toot() ) #HTL
        #タイムライン応答系
        ex.submit(th_worker)
        ex.submit(th_delete)
        ex.submit(th_status_saver)
        ex.submit(th_gettingnum)
        #スケジュール起動系
        ex.submit(th_kiri_scheduler,summarize_tooter,['02'])
        ex.submit(th_kiri_scheduler,bottlemail_sending,['05'])
        ex.submit(th_kiri_scheduler,monomane_tooter,None,20,-5,10)
        ex.submit(th_kiri_scheduler,lstm_tooter,None,20,-5,10)
        ex.submit(th_kiri_scheduler,timer_bst1st,None,20,-5,10)

if __name__ == '__main__':
    main()
