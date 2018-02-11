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
import warnings, traceback
BOT_ID = 'kiri_bot01'

#######################################################
# エラー時のログ書き込み
def error_log():
    jst_now = datetime.now(timezone('Asia/Tokyo'))
    ymdhms = jst_now.strftime("%Y/%m/%d %H:%M:%S")
    with open('error.log', 'a') as f:
        f.write('\n####%s####\n'%ymdhms)
        traceback.print_exc(file=f)
    print("###%s 例外情報\n"%ymdhms + traceback.format_exc())

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
            c.execute('insert into scoremanager (acct, score_getnum, score_fav,\
             datetime_fav, score_boost, datetime_boost,  score_reply, score_func)\
             values (?,?,?,?,?,?,?,?) ',(acct,i_score_getnum, i_score_fav,
              i_datetime_fav, i_score_boost, i_datetime_boost, i_score_reply, i_score_func) )
        else:
            r_acct, r_score_getnum, r_score_fav, r_datetime_fav, r_score_boost,\
             r_datetime_boost, r_score_reply, r_score_func   = row
            #print('row=',row)
            #にこ、ぶー爆はカウントしない
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

            #print(i_fav_time, r_fav_time, i_boost_time, r_boost_time, diff)

            c.execute('update scoremanager set score_getnum=?, score_fav=?, datetime_fav=?, score_boost=?, datetime_boost=?,  score_reply=?, score_func=? where acct=?',\
                (r_score_getnum+i_score_getnum, r_score_fav+i_score_fav, r_datetime_fav, r_score_boost+i_score_boost, r_datetime_boost, r_score_reply+i_score_reply, r_score_func+i_score_func, acct) )

        con.commit()
        con.close()

    def show(self):
        con = sqlite3.connect(self.DB_PATH)
        rows = con.execute('select * from scoremanager')
        return rows
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
    #トゥート先NGの人たちー！
    ng_user_set = set('friends_nico')
    STATUSES_DB_PATH = "db/statuses.db"
    def __init__(self):
        self.con = sqlite3.connect(self.STATUSES_DB_PATH,timeout = 60*1000)
        self.c = self.con.cursor()
        #NGワード
        self.ng_words = set(word.strip() for word in open('.ng_words').readlines())

    #######################################################
    # 指定された時間内から一人ユーザを選ぶ
    def sample_acct(self,delta):
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        ymd = int((jst_now - delta).strftime("%Y%m%d"))
        hh0000 = int((jst_now - delta).strftime("%H%M%S"))
        hh9999 = int(jst_now.strftime("%H%M%S"))
        if hh0000 > hh9999:
            hh9999 = 2359
        self.c.execute( r"select acct from statuses where (date = ?) and time >=\
                    ? and time <= ? and acct <> ?", [ymd,hh0000,hh9999,BOT_ID] )
        toots = ""
        acct_list = set([])
        for row in self.c.fetchall():
            acct_list.add(row[0])
        acct_list -= self.ng_user_set
        return random.sample(acct_list,1)[0]

    #######################################################
    # ブースト対象のトゥートを返す
    def get_random_1id(self,acct):
        if acct == None:
            return
        #self.c.execute( r"select id from statuses where acct = ? order by id asc", (acct,) )
        self.c.execute( r"select id from statuses where acct = ?", (acct,) )
        ids = []
        for i,row in enumerate(c.fetchall()):
            ids.append(row[0])
            if i >= 10000:
                break
        return random.sample(ids,1)[0]

    #######################################################
    # 直近１０トゥートを返す
    def get_least_10toots(self):
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        ymd = int(jst_now.strftime("%Y%m%d"))
        hh = jst_now.strftime("%H")
        hh0000 = int(hh + "0000")
        hh9999 = int(hh + "9999")
        self.c.execute( r"select content,id,acct from statuses where (date = ?) \
                and time >= ? and time <= ? and acct <> ? order by time desc"\
                , [ymd,hh0000,hh9999, BOT_ID] )
        seeds = []
        seedtxt = ''
        id = 0
        acct = ''
        for row in self.c.fetchall():
            content = content_cleanser(row[0])
            id = row[1]
            acct = row[2]
            if len(content) == 0:
                pass
            else:
                seeds.append(content)
                if len(seeds)>10:
                    break
        return seeds.reverse()

    #######################################################
    # ｉｄ指定でトゥート内容を返す
    def pickup_1toot(self,status_id):
            self.c.execute( r"select acct,content from statuses where id = ?",
                            (status_id,))
            row = self.c.fetchone()
            return row

    #######################################################
    # 数取りゲーム用 人数カウント
    def get_gamenum(self):
        #過去１５分のアクティブユーザ数をベース
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        ymd = int(jst_now.strftime("%Y%m%d"))
        hh0000 = int((jst_now - timedelta(minutes=5)).strftime("%H%M%S"))
        hh9999 = int(jst_now.strftime("%H%M%S"))
        if hh0000 > hh9999:
            hh0000 = 0
        try:
            #ランダムに人を選ぶよー！（最近いる人から）
            self.c.execute( r"select acct from statuses where (date = ?) and time >= ? and time <= ? and acct <> ?",[ymd,hh0000,hh9999,BOT_ID] )
            acct_list = set([])
            for row in self.c.fetchall():
                acct_list.add(row[0])

            return int(len(acct_list))

        except:
            error_log()
            return 0

    def get_user_toots(self,acct):
        self.c.execute( r"select content from statuses where acct = ?", (acct,) )
        return self.c.fetchall()

    def get_toots_1hour(self):
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        ymd = int((jst_now - timedelta(hours=1)).strftime("%Y%m%d"))
        hh = (jst_now - timedelta(hours=1)).strftime("%H")
        hh0000 = int(hh + "0000")
        hh9999 = int(hh + "9999")
        self.c.execute( r"select content from statuses where (date = ?) and time\
                >= ? and time <= ? and acct <> ?", (ymd,hh0000,hh9999,BOT_ID) )
        return self.c.fetchall()

    def save_toot(self, status):
        media_attachments = status["media_attachments"]
        mediatext = ""
        for media in media_attachments:
            mediatext += media["url"] + " "

        #jst_time = dateutil.parser.parse(str())
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
        insert_sql = u"insert into statuses (id, date, time, content, acct,\
                display_name, media_attachments) values (?, ?, ?, ?, ?, ?, ?)"
        try:
            self.c.execute(insert_sql, data)
            self.con.commit()
        except:
            pass

if __name__ == '__main__':
    pass
