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

class GettingNum():
    def __init__(self,maxval=10):
        #数取りゲームの上限値
        self.maxval = maxval
        #投票データ
        self.votedata = {}

    def vote(self,acct,num):
        if num < 1 or self.maxval < num:
            return False
        else:
            self.votedata[acct] = num
            return True

    def get_results(self):
        results = {}
        #初期化〜〜
        for i in range(1,self.maxval+1):
            results[i] = []

        for acct,num in self.votedata.items():
            results[num].append(acct)

        return results

#######################################################
# しりとり用
class Siritori_game():
    def __init__(self,MG,lv=None):
        self.MG = MG
        self.zumi = []
        self.sdict = {}
        self.lv = random.randint(1,50)
        if self.lv >= 40:
            self.lv = random.randint(40,60)
        for k,v in random.sample(self.MG.wdict.items(),len(self.MG.wdict)//(65-self.lv)):
            self.sdict[k] = v
        del_key = []
        for k,v in self.sdict.items():
            if v[-1] == 'ン':
                if random.randint(0,60) < self.lv:
                    del_key.append(k)
            elif len(k) > 4 + self.lv//4:
                del_key.append(k)
        for k in del_key:
            del self.sdict[k]

        self.rcnt = 0

    def judge(self,word):
        print('しりとり＝',word)
        if word[-1] in  ['ン','ん']:
            return False,'あ、「ん」で終わったー！'

        if word.strip() not in self.MG.wdict:
            return True,'知らない単語なので別の単語お願い！'

        if word in self.zumi:
            return False,'あ、一回言ったやつだー！'

        yomi = self.MG.wdict[word]
        if len(self.zumi) > 0: #前の言葉と繋がっているか
            word_1b = self.zumi[-1]
            yomi_1b = self.MG.wdict[word_1b]
            tail_1b = yomi_1b[-1]
            if tail_1b in ['ー','−']:
                tail_1b = yomi_1b[-2]
            if tail_1b in self.MG.yure:
                tail_1b = self.MG.yure[tail_1b]
            head = yomi[0]
            if head in self.MG.yure:
                head = self.MG.yure[head]
            if tail_1b != head:
                return True,'繋がってないよー！（%s【%s】）'%(word,yomi)

        if yomi[-1] == 'ン':
            return False,'「ん」で終わったー！（%s【%s】）'%(word,yomi)

        self.zumi.append(word)

        if word in self.sdict and random.randint(0,60) < self.lv:
            del self.sdict[word]
        self.rcnt += 1
        return True,'yes'

    def get_word(self,word):
        yomi = self.MG.wdict[word]
        tail = yomi[-1]
        if tail in ['ー','−']:
            tail = yomi[-2]
        if tail in self.MG.yure:
            tail = self.MG.yure[tail]

        kouho = {}
        for k,v in self.sdict.items():
            if v[0] == tail:
                kouho[k] = v

        if len(kouho) > 0:
            k,v = random.sample(kouho.items(),1)[0]
            tail = v[-1]
            if tail in ['ー','−']:
                tail = v[-2]
            if tail in self.MG.yure:
                tail = self.MG.yure[tail]
            return k,v,tail

        else:
            return None,None,None

    def random_choice(self):
        for a,b in random.sample(self.sdict.items(),100):
            tail = b[-1]
            if tail != 'ン':
                if tail in ['ー','−']:
                    tail = b[-2]
                if tail in self.MG.yure:
                    tail = self.MG.yure[tail]
                return a,b,tail

class Siritori_manager():
#しりとり用
    def __init__(self):
        self.wdict = { tmp.strip().split(',')[0]:tmp.strip().split(',')[1] for tmp in open('dic/siritori.csv').readlines() }
        self.games = {}
        self.yure = {'ァ':'ア','ィ':'イ','ゥ':'ウ','ェ':'エ','ォ':'オ','ャ':'ヤ','ュ':'ユ','ョ':'ヨ','ッ':'ツ','ヮ':'ワ','ヶ':'ケ'}

    def add_game(self,acct):
        self.games[acct] = Siritori_game(self)

    def end_game(self,acct):
        del self.games[acct]

    def is_game(self,acct):
        if acct in self.games:
            return True
        else:
            return False


"""
class Hunting():
    def __init__(self):
        pass

    def update_user_status(self):

"""
#if __name__ == '__main__':
