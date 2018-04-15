# coding: utf-8

import random,json
import os,sys,io,re
from time import sleep
import unicodedata
import sqlite3
import threading
from pytz import timezone
from dateutil import parser
from datetime import datetime,timedelta
from bs4 import BeautifulSoup
import warnings, traceback
from googletrans import Translator
import cv2
BOT_ID = 'kiri_bot01'

#######################################################
# ネイティオ語翻訳
def two2jp(twotwo_text):
    twotwodic = {}
    twotwo_text = unicodedata.normalize("NFKC", twotwo_text)
    for line in open('dic/twotwo.dic'):
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
# エラー時のログ書き込み
def error_log():
    jst_now = datetime.now(timezone('Asia/Tokyo'))
    ymdhms = jst_now.strftime("%Y/%m/%d %H:%M:%S")
    with open('error.log', 'a') as f:
        f.write('\n####%s####\n'%ymdhms)
        traceback.print_exc(file=f)
    print("###%s 例外情報\n"%ymdhms + traceback.format_exc())

#######################################################
# ハッシュタグ抽出
def hashtag(content):
    tmp = BeautifulSoup(content.replace("<br />","___R___").strip(),'lxml')
    hashtag = []
    for x in tmp.find_all("a",rel="tag"):
        hashtag.append(x.span.text)
    return ','.join(hashtag)

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
    rtext = re.sub(r'([^:])@', r'\1', rtext)
    rtext = rtext.replace("#","")
    rtext = re.sub(r'(___R___)\1{2,}', r'\1', rtext)
    rtext = re.sub(r'___R___', r'\n', rtext)
    #NGワード
    ng_words = set(word.strip() for word in open('.ng_words').readlines())
    for ng_word in ng_words:
        # rtext = rtext.replace(ng_word,'■■■')
        rtext = re.sub(ng_word, '■■■', rtext)
    if hashtag != "":
        return rtext + " #" + hashtag
    else:
        return rtext

#######################################################
# スケジューラー！
def scheduler(func,mms=None,intvl=60,rndmin=0,rndmax=0,CM=None):
    #func:起動する処理
    #mm:起動時刻（分）
    #intmm:起動間隔（分）
    while True:
        sleep(5)
        try:
            #時刻指定がなければ、インターバル分＋流速考慮値
            if mms == None:
                if rndmin == 0 and rndmax == 0 or rndmin >= rndmax:
                    rndmm = 0
                else:
                    rndmm = random.randint(rndmin,rndmax)
                if CM==None:
                    cmm = 0
                else:
                    cmm = int(CM.get_coolingtime())
                a = (intvl+cmm+rndmm)*60
                print('###%s###  start at : %ds'%(func,a))
                sleep(a)
                func()
            else:
                #以降は時刻指定時の処理
                jst_now = datetime.now(timezone('Asia/Tokyo'))
                mm = jst_now.strftime("%M")
                #print('###%s###  start at: **:%s'%(func,mms))
                if mm in mms:
                    func()
                    sleep(60)
        except Exception:
            error_log()

#######################################################
# スコア管理
class ScoreManager():
    DB_PATH = "db/scoremanager.db"
    DB_SCHEMA_PATH = "scoremanager.sql"
    def __init__(self, db=None):
        if db is not None:
            self.DB_PATH = db

        # DBがない場合、作る！
        if not os.path.exists(self.DB_PATH):
            con = sqlite3.connect(self.DB_PATH)
            with open(self.DB_SCHEMA_PATH, "r") as f:
                schema = f.read()
                con.execute(schema)

            con.commit()
            con.close()

    def update(self,acct,key,i_datetime=None,score=1):
        if acct == None or key == None:
            return

        i_score_getnum, i_score_fav, i_datetime_fav, i_score_boost, i_datetime_boost,\
         i_score_reply, i_score_func = 0,0,None,0,None,0,0

        #振り分け
        if key == 'getnum':
            i_score_getnum = score
        elif key == 'fav':
            i_score_fav = score
            i_datetime_fav = i_datetime
        elif key == 'boost':
            i_score_boost = score
            i_datetime_boost = i_datetime
        elif key == 'reply':
            i_score_reply = score
        elif key == 'func':
            i_score_func = score

        con = sqlite3.connect(self.DB_PATH)
        c = con.cursor()
        c.execute( r"select * from scoremanager where acct = ?",(acct,))
        row = c.fetchone()
        if row == None:
            c.execute('insert into scoremanager (acct, score_getnum, score_fav, datetime_fav, score_boost, datetime_boost,  score_reply, score_func) values (?,?,?,?,?,?,?,?) ',
                        (acct,i_score_getnum, i_score_fav, i_datetime_fav, i_score_boost, i_datetime_boost, i_score_reply, i_score_func) )
        else:
            r_acct, r_score_getnum, r_score_fav, r_datetime_fav, r_score_boost,\
                r_datetime_boost, r_score_reply, r_score_func   = row
            if i_datetime_fav == None:
                i_fav_time   = None
            else:
                i_fav_time   = parser.parse(i_datetime_fav  ).astimezone(timezone('Asia/Tokyo'))

            if r_datetime_fav == None:
                r_fav_time   = None
            else:
                r_fav_time   = parser.parse(r_datetime_fav  ).astimezone(timezone('Asia/Tokyo'))

            if i_datetime_boost == None:
                i_boost_time = None
            else:
                i_boost_time = parser.parse(i_datetime_boost).astimezone(timezone('Asia/Tokyo'))

            if r_datetime_boost == None:
                r_boost_time = None
            else:
                r_boost_time = parser.parse(r_datetime_boost).astimezone(timezone('Asia/Tokyo'))

            diff = timedelta(seconds=30)
            if i_fav_time == None:
                i_score_fav = 0
            elif r_fav_time != None and i_fav_time < r_fav_time + diff:
                i_score_fav = 0
            if i_datetime_fav != None:
                r_datetime_fav = i_datetime_fav

            if i_boost_time == None:
                i_score_boost = 0
            elif r_boost_time != None and i_boost_time < r_boost_time + diff:
                i_score_boost = 0

            if i_datetime_boost != None:
                r_datetime_boost = i_datetime_boost

            c.execute('update scoremanager set score_getnum=?, score_fav=?, datetime_fav=?, score_boost=?, datetime_boost=?,  score_reply=?, score_func=? where acct=?',\
                (r_score_getnum+i_score_getnum, r_score_fav+i_score_fav, r_datetime_fav, r_score_boost+i_score_boost, r_datetime_boost, r_score_reply+i_score_reply, r_score_func+i_score_func, acct) )

        con.commit()
        con.close()

    def show(self):
        con = sqlite3.connect(self.DB_PATH)
        rows = con.execute('select * from scoremanager')
        return rows.fetchall()
        con.close()

#######################################################
# クーリングタイム管理
class CoolingManager():
    def __init__(self,base_time=10):
        self.base_time = base_time
        self.created_ats = []
        threading.Thread(target=self.timer_showflowrate).start()

    def count(self,created_at):
        #print(type(created_at),created_at.astimezone(timezone('Asia/Tokyo')))
        self.created_ats.append(created_at.astimezone(timezone('Asia/Tokyo')))
        if len(self.created_ats) > 100:
            self.created_ats = self.created_ats[1:]

    def _flowrate(self):  # toot数/分 を返す
        if len(self.created_ats) > 10:
            delta = self.created_ats[-1] - self.created_ats[0]
            return len(self.created_ats)*60 /delta.total_seconds()
        else:
            return 60

    def timer_showflowrate(self):
        while True:
            sleep(60)
            print('***流速:{0:.1f}toots/分'.format( self._flowrate() ))

    def get_coolingtime(self):
        return self._flowrate() * self.base_time / 60


#######################################################
# きりたんタイマー
class KiriTimer():
    def __init__(self,time=300):
        self.time_org = time
        self.time = time
        self.start_fg = False

    def _timer(self):
        while True:
            sleep(1)
            self.time -= 1
            if self.time <= 0:
                self.time = 0
                self.start_fg = False
                return

    def start(self):
        if  self.start_fg == False:
            self.start_fg = True
            threading.Thread(target=self._timer).start()

    def check(self):
        if self.time < 0:
            return 0
        else:
            return self.time

    def reset(self, time=None):
        if time == None:
            self.time = self.time_org
        else:
            self.time = time


#######################################################
# きりたんだお〜！
class DAO_statuses():
    def __init__(self):
        #path
        self.STATUSES_DB_PATH = "db/statuses.db"
        #トゥート先NGの人たちー！
        self.ng_user_set = set('friends_nico')

    #######################################################
    # 指定された時間内から一人ユーザを選ぶ
    def sample_acct(self):
        acct_list = set([])
        con = sqlite3.connect(self.STATUSES_DB_PATH,timeout = 60*1000)
        c = con.cursor()
        sql = r"select acct from statuses where acct <> ? order by id desc"
        for row in c.execute(sql , [BOT_ID,] ) :
            acct_list.add(row[0])
            if len(acct_list)>30:
                break
        acct_list -= self.ng_user_set
        con.close()

        return random.sample(acct_list,1)[0]

    #######################################################
    # ブースト対象のトゥートを返す
    def get_random_1id(self,acct):
        if acct == None:
            return
        ids = []
        con = sqlite3.connect(self.STATUSES_DB_PATH,timeout = 6*1000)
        c = con.cursor()
        sql = r"select id from statuses where acct = ?  order by id asc"
        for row in c.execute( sql, (acct,)):
            ids.append(row[0])
        con.close()
        return random.sample(ids,1)[0]

    #######################################################
    # 直近１０トゥートを返す
    def get_least_10toots(self):
        seeds = []
        con = sqlite3.connect(self.STATUSES_DB_PATH,timeout = 6*1000)
        c = con.cursor()
        sql = r"select content from statuses order by id desc"
        for row in c.execute(sql):
            content = content_cleanser(row[0])
            #print('get_least_10toots content=',content)
            if len(content) == 0:
                continue
            else:
                seeds.append(content)
                if len(seeds)>10:
                    break
        con.close()
        seeds.reverse()
        return seeds

    #######################################################
    # ｉｄ指定でトゥート内容を返す
    def pickup_1toot(self,status_id):
        con = sqlite3.connect(self.STATUSES_DB_PATH,timeout = 6*1000)
        c = con.cursor()
        c.execute( r"select acct, content, date, time  from statuses where id = ?",
                        (status_id,))
        row = c.fetchone()
        con.close()
        return row

    #######################################################
    # 数取りゲーム用 人数カウント
    def get_gamenum(self):
        #過去５分のアクティブユーザ数をベース
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        ymd = int(jst_now.strftime("%Y%m%d"))
        hh0000 = int((jst_now - timedelta(minutes=5)).strftime("%H%M%S"))
        hh9999 = int(jst_now.strftime("%H%M%S"))
        if hh0000 > hh9999:
            hh0000 = 0
        #ランダムに人を選ぶよー！（最近いる人から）
        con = sqlite3.connect(self.STATUSES_DB_PATH,timeout = 6*1000)
        c = con.cursor()
        c.execute( r"select acct from statuses where (date = ?) and time >= ? and time <= ? and acct <> ?",[ymd,hh0000,hh9999,BOT_ID] )
        acct_list = set([])
        for row in c.fetchall():
            acct_list.add(row[0])

        con.close()
        return len(acct_list)

    #######################################################
    # モノマネ用
    def get_user_toots(self,acct):
        con = sqlite3.connect(self.STATUSES_DB_PATH,timeout = 6*1000)
        c = con.cursor()
        c.execute( r"select content from statuses where acct = ?", (acct,) )
        rows = c.fetchall()
        con.close()
        return rows

    #######################################################
    # ここ1時間の要約
    def get_toots_1hour(self):
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        ymd = int((jst_now - timedelta(hours=1)).strftime("%Y%m%d"))
        hh = (jst_now - timedelta(hours=1)).strftime("%H")
        hh0000 = int(hh + "0000")
        hh9999 = int(hh + "9999")
        con = sqlite3.connect(self.STATUSES_DB_PATH,timeout = 6*1000)
        c = con.cursor()
        c.execute( r"select content from statuses where (date = ?) and time >= ? and time <= ? and acct <> ?",
                    (ymd,hh0000,hh9999,BOT_ID) )
        rows = c.fetchall()
        con.close()
        return rows

    #######################################################
    # トゥートの保存
    def save_toot(self, status):
        media_attachments = status["media_attachments"]
        mediatext = ""
        for media in media_attachments:
            mediatext += media["url"] + " "
        jst_time = status['created_at'].astimezone(timezone('Asia/Tokyo'))
        fmt = "%Y%m%d"
        tmpdate = jst_time.strftime(fmt)
        fmt = "%H%M%S"
        tmptime = jst_time.strftime(fmt)
        data = (str(status['id']),
                    tmpdate,
                    tmptime,
                    status['content'],
                    status['account']['acct'],
                    status['account']['display_name'],
                    mediatext
                    )
        con = sqlite3.connect(self.STATUSES_DB_PATH,timeout = 6*1000)
        c = con.cursor()
        insert_sql = u"insert into statuses (id, date, time, content, acct,\
                display_name, media_attachments) values (?, ?, ?, ?, ?, ?, ?)"
        try:
            c.execute(insert_sql, data)

        except sqlite3.IntegrityError:
            pass
        except sqlite3.Error:
            raise
        else:
            con.commit()
        finally:
            con.close()

    #######################################################
    # 対象の人の最新のトゥート日付を取得（新規さん等はNoneを返す）
    def get_least_created_at(self,acct):
        con = sqlite3.connect(self.STATUSES_DB_PATH,timeout = 6*1000)
        c = con.cursor()
        c.execute( r"select date, time from statuses where acct = ? order by id desc ", (acct,))
        row = c.fetchone()
        con.close()
        if row:
            date = '{0:08d}'.format(row[0])
            time = '{0:06d}'.format(row[1])
            ymdhms = '%s %s'%(date,time)
            return parser.parse(ymdhms).astimezone(timezone('Asia/Tokyo'))
        else:
            return None


def kiri_trans_xx2ja(lang, text):
    tor = Translator()
    return tor.translate(text, src=lang, dest='ja').text

def kiri_trans_ja2en(text):
    tor = Translator()
    return tor.translate(text, src='ja', dest='en').text

def kiri_trans_detect(text):
    tor = Translator()
    return tor.detect(text).lang


def face_search(image_path):
    try:
        #HAAR分類器の顔検出用の特徴量
        # cascade_path = "haarcascades/haarcascade_frontalface_default.xml"
        # cascade_path = "haarcascades/haarcascade_frontalface_alt.xml"
        # cascade_path = "haarcascades/haarcascade_frontalface_alt2.xml"
        cascade_path = "haarcascades/haarcascade_frontalface_alt_tree.xml"

        color = ( 5, 5, 200) #赤
        #color = (0, 0, 0) #黒

        #ファイル読み込み
        image = cv2.imread(image_path)
        #グレースケール変換
        image_gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        # print( image_gray)

        #カスケード分類器の特徴量を取得する
        cascade = cv2.CascadeClassifier(cascade_path)

        #物体認識（顔認識）の実行
        #image – CV_8U 型の行列．ここに格納されている画像中から物体が検出されます
        #objects – 矩形を要素とするベクトル．それぞれの矩形は，検出した物体を含みます
        #scaleFactor – 各画像スケールにおける縮小量を表します
        #minNeighbors – 物体候補となる矩形は，最低でもこの数だけの近傍矩形を含む必要があります
        #flags – このパラメータは，新しいカスケードでは利用されません．古いカスケードに対しては，cvHaarDetectObjects 関数の場合と同じ意味を持ちます
        #minSize – 物体が取り得る最小サイズ．これよりも小さい物体は無視されます
        facerect = cascade.detectMultiScale(image, scaleFactor=1.1, minNeighbors=1, minSize=(48, 48))

        print( "face rectangle")
        print( facerect)

        if len(facerect) > 0:
            #検出した顔を囲む矩形の作成
            for rect in facerect:
                cv2.rectangle(image, tuple(rect[0:2]),tuple(rect[0:2]+rect[2:4]), color, thickness=3)

            #認識結果の保存
            # save_path = ('media/detected.jpg')
            save_path = 'media/' + image_path.rsplit('/',1)[-1].split('.')[0] + '_face.jpg'
            cv2.imwrite(save_path, image)
            return save_path
    except Exception as e:
        print(e)
        return None
        
if __name__ == '__main__':
    images = []
    for f in os.listdir('media/'):
        # print('media/' + f)
        images.append('media/' + f)

    print(face_search(random.choice(images)))

    # while True:
    #     s = input()
    #     lang = kiri_trans_detect(s)
    #     if lang == 'en':
    #         t1 = kiri_trans_en2ja(lang, s)
    #         print(t1)
    #         t2 = kiri_trans_ja2en(t1)
    #         print(t2)
    #     elif lang == 'ja':
    #         t1 = kiri_trans_ja2en(s)
    #         print(t1)
    #         t2 = kiri_trans_en2ja(t1)
    #         print(t2)

"""
    sm = ScoreManager()
    score = {}
    for row in sm.show():
        score[row[0]] = row[2] + row[4] + row[6] + row[7]

    for i,row in enumerate( sorted(score.items(), key=lambda x: x[1])):
        print("%2d位:@%s: %d"%(i+1,row[0],row[1]))
        if i > 20:
            break
"""
