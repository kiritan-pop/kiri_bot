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

        i_score_getnum, i_score_fav, i_datetime_fav, i_score_boost, i_datetime_boost, i_score_reply, i_score_func = \
        0,0,None,0,None,0,0

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
            c.execute('insert into scoremanager (acct, score_getnum, score_fav, datetime_fav, score_boost, datetime_boost,  score_reply, score_func)\
             values (?,?,?,?,?,?,?,?) ',(acct,i_score_getnum, i_score_fav, i_datetime_fav, i_score_boost, i_datetime_boost, i_score_reply, i_score_func) )
        else:
            r_acct, r_score_getnum, r_score_fav, r_datetime_fav, r_score_boost, r_datetime_boost, r_score_reply, r_score_func \
                = row
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

if __name__ == '__main__':
    SM = ScoreManager()
#    SM.update('test001','fav','20180127 193859')
#    SM.update('test001','fav','20180127 193829')
#    SM.update('test001','getnum',score=-1)
#    SM.update('test001','boost','20180127 194000')
#    SM.update('test001','boost','20180127 194159')
#    SM.update('test001','func',score=-1)
#    SM.update('test001','reply')

    for ret in SM.show():
        print(ret)
