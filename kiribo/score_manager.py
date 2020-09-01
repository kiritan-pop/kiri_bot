# coding: utf-8

import os
import sqlite3
from pytz import timezone
from dateutil import parser
from datetime import datetime,timedelta

#######################################################
# スコア管理
class ScoreManager():
    DB_PATH = "data/scoremanager.db"
    DB_SCHEMA_PATH = "sql/scoremanager.sql"
    def __init__(self, db=None, timeout=3):
        self.timeout = timeout
        if db is not None:
            self.DB_PATH = db

        # DBがない場合、作る！
        if not os.path.exists(self.DB_PATH):
            con = sqlite3.connect(self.DB_PATH, timeout=self.timeout, isolation_level='EXCLUSIVE')
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

        con = sqlite3.connect(self.DB_PATH, timeout=self.timeout, isolation_level='EXCLUSIVE')
        c = con.cursor()
        c.execute( r"select * from scoremanager where acct = ?",(acct,))
        row = c.fetchone()
        if row == None:
            c.execute('insert into scoremanager (acct, score_getnum, score_fav, datetime_fav, score_boost, datetime_boost,  score_reply, score_func) values (?,?,?,?,?,?,?,?) ',
                        (acct,i_score_getnum, i_score_fav, i_datetime_fav, i_score_boost, i_datetime_boost, i_score_reply, i_score_func) )
        else:
            _, r_score_getnum, r_score_fav, r_datetime_fav, r_score_boost,\
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

    def show(self,acct=None):
        con = sqlite3.connect(self.DB_PATH, timeout=self.timeout, isolation_level='DEFERRED')
        if acct == None:
            rows = con.execute('select * from scoremanager')
        else:
            rows = con.execute('select * from scoremanager where acct=?',(acct,))
        ret = list(rows.fetchall())
        con.close()
        return ret

if __name__ == '__main__':
    from pprint import pprint as pp
    cm = ScoreManager()
    acct = "neruru"
    pp(cm.show(acct=acct))
    cm.update(acct=acct, key='getnum', score=480)
    pp(cm.show(acct=acct))
