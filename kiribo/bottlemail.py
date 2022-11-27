# coding: utf-8

import random,json
import os,sys,io,re
from time import sleep
import unicodedata
import sqlite3

# きりぼコンフィグ
from kiribo.config import BOTTLEMAIL_DB_PATH, BOTTLEMAIL_SCHEMA_PATH

class Bottlemail():
    DB_PATH = BOTTLEMAIL_DB_PATH
    DB_SCHEMA_PATH = BOTTLEMAIL_SCHEMA_PATH
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

    def bottling(self,acct,msg,reply_id):
        if acct == None or msg == None:
            return
        con = sqlite3.connect(self.DB_PATH)
        con.execute('insert into bottlemail (acct, msg, count, send_fg, reply_id) values (?,?,?,?,?) ',(acct,msg,0,0,reply_id))
        con.commit()
        con.close()

    def drifting(self):
        con = sqlite3.connect(self.DB_PATH)
        arrival = []
        #カウントランダムアップ
        for row in con.execute('select * from bottlemail'):
            con.execute('update bottlemail set count=? where id=? and send_fg=?',(row[3]+int(random.gauss(1,10)), row[0],0))
        con.commit()

        #カウント＞nの人抽出
        for row in con.execute('select * from bottlemail where count>=? and send_fg=?',(2000,0)):
            arrival.append([row[0],row[1],row[2],row[6]])
        con.close()
        #送信対象を返すよー！
        return arrival

    def sended(self, id, dest):
        if id == None or dest == None:
            return
        con = sqlite3.connect(self.DB_PATH)
        #送信済み更新
        for row in con.execute('select * from bottlemail'):
            con.execute('update bottlemail set send_fg=?,dest=? where id=?',(1, dest, id))
        con.commit()
        con.close()

    def show(self):
        con = sqlite3.connect(self.DB_PATH)
        rows = con.execute('select * from bottlemail')
        return rows
        con.close()

    def show_flow(self):
        con = sqlite3.connect(self.DB_PATH)
        rows = con.execute('select * from bottlemail where send_fg=0')
        return rows
        con.close()

    def flow_count(self):
        con = sqlite3.connect(self.DB_PATH)
        c = con.cursor()
        c.execute('select count(*) from bottlemail where send_fg=0')
        result = c.fetchone()
        con.close()
        return result[0]

if __name__ == '__main__':
    bm = Bottlemail()
    for ret in bm.show():
        print(ret)
    print(bm.flow_count())
