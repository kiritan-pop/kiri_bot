# coding: utf-8

import random,json
import os,sys,io,re
from time import sleep
import unicodedata
import sqlite3


class Bottlemail():
    DB_PATH = "db/bottlemail.db"
    DB_SCHEMA_PATH = "bottlemail.sql"
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

    def bottling(self,acct,msg):
        if acct == None or msg == None:
            return
        con = sqlite3.connect(self.DB_PATH)
        con.execute('insert into bottlemail (acct, msg, count, send_fg) values (?,?,?,?) ',(acct,msg,0,0))
        con.commit()
        con.close()

    def test(self):
        con = sqlite3.connect(self.DB_PATH)
        for row in con.execute('select * from bottlemail'):
            print(row)
        con.close()

    def drifting(self):
        con = sqlite3.connect(self.DB_PATH)
        arrival = []
        #カウントランダムアップ
        for row in con.execute('select * from bottlemail'):
            con.execute('update bottlemail set count=? where id=? and send_fg=?',(row[3]+random.randint(1,10), row[0],0))
        con.commit()

        #カウント＞100の人抽出
        for row in con.execute('select * from bottlemail where count>=? and send_fg=?',(100,0)):
            arrival.append([row[0],row[1],row[2]])
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


if __name__ == '__main__':
    bm = Bottlemail()
    #bm.bottling('kiritan5','テストメッセージ3')
    #list = bm.drifting()
    #print(list)
    #for id,acct,msg in list:
    #    print(id)
    #    print(acct)
    #    print(msg)
    #    bm.sended(id,'kiri_bot01')

    bm.test()
