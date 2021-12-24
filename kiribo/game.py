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

# きりぼコンフィグ
from kiribo.config import SIRITORI_DIC_PATH
import logging

logger = logging.getLogger(__name__)

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
        if self.lv >= 45:
            self.lv = random.randint(45,60)
        for k,v in random.sample(self.MG.wdict.items(),len(self.MG.wdict)//(21-self.lv//5)):
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
        logger.info(f"しりとり＝{word}")
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
        self.wdict = { tmp.strip().split(',')[0]:tmp.strip().split(',')[1] for tmp in open(SIRITORI_DIC_PATH).readlines() }
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


class Jinro_Manager():
    def __init__(self):
        self.accts = {}
        self.turncnt = 0

    def set_game(self,acct_list):
        for acct in acct_list:
            self.accts[acct] = {}


class Friends_nico_slot():
    def __init__(self,acct,o_accts,rate=1,reelsize=6):
        self.ot_base_rate = [0,0,0,10,50,100]
        self.ac_base_rate = [0,0,0,50,250,1000]
        self.acct = acct
        self.rate = rate
        #リール作成
        self.reels = []
        temp = []
        for a in o_accts:
            # temp.append(a)
            temp.append(':@%s:'%a)
        temp2 = []
        for a in temp:
            temp2.extend([a for _ in range(reelsize)])
        temp2.extend([ ':@'+acct+':' for _ in range(3)])
        for _ in range(5):
            random.shuffle(temp2)
            self.reels.append(temp2)

    def start(self):
        cols = [[] for _ in range(5)]
        rows = [[] for _ in range(3)]
        #リール回転
        for i in range(5):
            sel = random.randrange(0,len(self.reels[i]))
            if sel == 0:
                sel_u = len(self.reels[i])-1
            else:
                sel_u = sel - 1
            if sel == len(self.reels[i])-1:
                sel_r = 0
            else:
                sel_r = sel + 1

            cols[i] = [self.reels[i][sel_u],self.reels[i][sel],self.reels[i][sel_r]]

        for i in range(3):
            for j in range(5):
                rows[i].append(cols[j][i])

        #当たり判定
        cnt_list = []
        hit_acct_list = []
        for i in range(3):
            cnt = 1
            hit_acct = ''
            for j in range(4):
                if rows[i][j] == rows[i][j+1]:
                    cnt += 1
                    hit_acct = rows[i][j]
                else:
                    if cnt < 3:
                        cnt = 1
                        hit_acct = ''
                    else:
                        break

            if cnt > 2:
                cnt_list.append(cnt)
                hit_acct_list.append(hit_acct)

        #得点カウント
        score = 0
        for c,ac in zip(cnt_list,hit_acct_list):
            if ac == ':@'+self.acct+':' :
                score += self.ac_base_rate[c]*self.rate
            else:
                score += self.ot_base_rate[c]*self.rate

        return rows,int(score)

"""
class Hunting():
    def __init__(self):
        pass

    def update_user_status(self):

"""
if __name__ == '__main__':
    g = Friends_nico_slot('kiritan',['yesdotsam', 'JC','rept', 'Thiele'],1,5) #,'aaa','bbb','ccc','ddd'

    game_cnt = 10000
    score_sum = 0
    for i in range(game_cnt):
        rows,score = g.start()
        score_sum += score
    print(score_sum,(score_sum)/game_cnt/3)

