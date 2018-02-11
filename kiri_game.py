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

"""
class Hunting():
    def __init__(self):
        pass

    def update_user_status(self):

"""
#if __name__ == '__main__':
