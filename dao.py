# coding: utf-8

import os
import sqlite3
import random
from pytz import timezone
from dateutil import parser
from datetime import datetime,timedelta

# きりぼコンフィグ
from config import STATUSES_DB_PATH, DB_SCHEMA_PATH

import util

#######################################################
# きりたんだお〜！
class Dao():
    def __init__(self, timeout=3, bot_id="kiri_bot"):
        self.timeout = timeout
        self.bot_id = bot_id
        #トゥート先NGの人たちー！
        self.ng_user_set = set()

        # DBがない場合、作る！
        if not os.path.exists(STATUSES_DB_PATH):
            con = sqlite3.connect(
                STATUSES_DB_PATH, timeout=self.timeout, isolation_level='EXCLUSIVE')
            with open(DB_SCHEMA_PATH, "r") as f:
                schema = f.read()

            con.execute(schema)
            con.commit()
            con.close()

    #######################################################
    # 指定された時間内から一人ユーザを選ぶ
    def sample_acct(self):
        acct_list = set([])
        con = sqlite3.connect(STATUSES_DB_PATH, timeout=self.timeout, isolation_level='DEFERRED')
        c = con.cursor()
        sql = r"select distinct acct from statuses where acct <> ? order by id desc limit 30"
        for row in c.execute(sql , [self.bot_id,] ) :
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
        con = sqlite3.connect(STATUSES_DB_PATH, timeout=self.timeout, isolation_level='DEFERRED')
        c = con.cursor()
        sql = r"select id from statuses where acct = ?  order by id asc"
        for row in c.execute( sql, (acct,)):
            ids.append(row[0])
        con.close()
        return random.sample(ids,1)[0]

    #######################################################
    # 直近１０トゥートを返す
    def get_least_10toots(self,acct=None,limit=15, time=False):
        seeds = []
        con = sqlite3.connect(STATUSES_DB_PATH, timeout=self.timeout, isolation_level='DEFERRED')
        c = con.cursor()
        if time:
            sql = r"select content,date,time from statuses order by id desc limit ?"
            exe = c.execute(sql,(limit,))
            for row in exe:
                content = util.content_cleanser(row[0])
                ymdhms = f'{row[1]:08d} {row[2]:06d}'
                ymdhms = parser.parse(ymdhms).astimezone(timezone('Asia/Tokyo'))
                if len(content) == 0:
                    continue
                else:
                    seeds.append((content,ymdhms))
            con.close()
            seeds.reverse()
            return seeds
        else:
            sql = r"select content from statuses order by id desc limit ?"
            exe = c.execute(sql,(limit,))
            for row in exe:
                content = util.content_cleanser(row[0])
                if len(content) == 0:
                    continue
                else:
                    seeds.append(content)
            con.close()
            seeds.reverse()
            return seeds



    #######################################################
    # ｉｄ指定でトゥート内容を返す
    def pickup_1toot(self,status_id):
        con = sqlite3.connect(STATUSES_DB_PATH, timeout=self.timeout, isolation_level='DEFERRED')
        c = con.cursor()
        c.execute( r"select acct, content, date, time  from statuses where id = ?",
                        (status_id,))
        row = c.fetchone()
        con.close()
        return row

    #######################################################
    # 数取りゲーム用 人数カウント
    def get_gamenum(self, minutes=5):
        #過去n分のアクティブユーザ数をベース
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        ymd = int((jst_now - timedelta(minutes=minutes)).strftime("%Y%m%d"))
        hms = int((jst_now - timedelta(minutes=minutes)).strftime("%H%M%S"))
        ymd2 = int(jst_now.strftime("%Y%m%d"))
        hms2 = int(jst_now.strftime("%H%M%S"))

        con = sqlite3.connect(STATUSES_DB_PATH, timeout=self.timeout, isolation_level='DEFERRED')
        c = con.cursor()
        if ymd == ymd2 and int(hms) <= int(hms2):
            c.execute( r"select distinct acct from statuses where (date = ? and time >= ? and time <= ? )",
                        (ymd,hms,hms2) )
        else:
            c.execute( r"select distinct acct from statuses where (date = ? and time >= ?) or (date = ? and time <= ? ) or (date > ? and date < ?)",
                        (ymd,hms,ymd2,hms2,ymd,ymd2) )
        acct_list = set([])
        for row in c.fetchall():
            acct_list.add(row[0])

        con.close()
        return len(acct_list)

    #######################################################
    # 陣形用５人ピックアップ
    def get_five(self, num=5,minutes=30):
        #アクティブユーザ数ピックアップ
        con = sqlite3.connect(STATUSES_DB_PATH, timeout=self.timeout, isolation_level='DEFERRED')
        c = con.cursor()
        c.execute( r"select distinct acct from statuses order by id desc limit 20")
        acct_list = set([])
        for row in c.fetchall():
            acct_list.add(row[0])
        con.close()
        return random.sample(acct_list,min([num, len(acct_list)]))

    #######################################################
    # モノマネ用
    def get_user_toots(self, acct, limit=10):
        con = sqlite3.connect(STATUSES_DB_PATH, timeout=self.timeout, isolation_level='DEFERRED')
        c = con.cursor()
        c.execute( r"select id, content, date, time from statuses where acct = ? order by id asc limit ?", (acct,limit) )
        rows = c.fetchall()
        con.close()
        return rows

    #######################################################
    # 時間指定トゥート取得
    def get_toots_hours(self, hours=1):
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        ymd = int((jst_now - timedelta(hours=hours)).strftime("%Y%m%d"))
        hms = int((jst_now - timedelta(hours=hours)).strftime("%H%M%S"))
        ymd2 = int(jst_now.strftime("%Y%m%d"))
        hms2 = int(jst_now.strftime("%H%M%S"))
        con = sqlite3.connect(STATUSES_DB_PATH, timeout=self.timeout, isolation_level='DEFERRED')
        c = con.cursor()
        if ymd == ymd2 and int(hms) <= int(hms2):
            c.execute( r"select acct,count(content) from statuses where (date = ? and time >= ? and time <= ? ) group by acct",
                        (ymd,hms,hms2) )
        else:
            c.execute( r"select acct,count(content) from statuses where (date = ? and time >= ?) or (date = ? and time <= ? ) or (date > ? and date < ?) group by acct",
                        (ymd,hms,ymd2,hms2,ymd,ymd2) )

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
        con = sqlite3.connect(STATUSES_DB_PATH, timeout=self.timeout, isolation_level='EXCLUSIVE')
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
    # 対象の人のh時間以内のトゥート日付を取得
    def get_least_created_at(self,acct,h=3):
        # con = sqlite3.connect(STATUSES_DB_PATH, timeout=self.timeout, isolation_level='DEFERRED')
        # c = con.cursor()
        # c.execute( r"select date, time from statuses where acct = ? order by id desc limit 1", (acct,))
        jst_now = datetime.now(timezone('Asia/Tokyo'))
        ymd = int((jst_now - timedelta(hours=h)).strftime("%Y%m%d"))
        hms = int((jst_now - timedelta(hours=h)).strftime("%H%M%S"))
        ymd2 = int(jst_now.strftime("%Y%m%d"))
        hms2 = int(jst_now.strftime("%H%M%S"))

        con = sqlite3.connect(STATUSES_DB_PATH, timeout=self.timeout, isolation_level='DEFERRED')
        c = con.cursor()
        if ymd == ymd2 and int(hms) <= int(hms2):
            c.execute( r"select date, time from statuses where acct = ? and (date = ? and time >= ? and time <= ? ) limit 1",
                        (acct,ymd,hms,hms2) )
        else:
            c.execute( r"select date, time  from statuses where acct = ? and ((date = ? and time >= ?) or (date = ? and time <= ? ) or (date > ? and date < ?)) limit 1",
                        (acct,ymd,hms,ymd2,hms2,ymd,ymd2) )

        row = c.fetchone()
        con.close()
        if row:
            date = '{0:08d}'.format(row[0])
            time = '{0:06d}'.format(row[1])
            ymdhms = '%s %s'%(date,time)
            return parser.parse(ymdhms).astimezone(timezone('Asia/Tokyo'))
        else:
            return None
