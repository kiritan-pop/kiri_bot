# coding: utf-8

from time import sleep
from datetime import datetime
import threading
import random

# きりぼコンフィグ
from kiribo.config import settings
import logging
logger = logging.getLogger(__name__)

#######################################################
# スケジューラー！
class Scheduler():
    def __init__(self, func, hhmm_list, intvl=60, rndmin=0, rndmax=0, cm=None):
        if hhmm_list:
            self.th = threading.Thread(target=self.scheduler, args=(func, hhmm_list)) 
        else:
            self.th = threading.Thread(target=self.scheduler_rnd, args=(func, intvl, rndmin, rndmax, cm)) 

    def scheduler(self, func, hhmm_list):
        #func:起動する処理
        #hhmm_list:起動時刻
        while True:
            sleep(10)
            try:
                #時刻指定時の処理
                jst_now = datetime.now(settings.timezone)
                hh_now = jst_now.strftime("%H")
                mm_now = jst_now.strftime("%M")
                for hhmm in hhmm_list:
                    if len(hhmm.split(":")) == 2:
                        hh,mm = hhmm.split(":")
                        if (hh == hh_now or hh == '**') and mm == mm_now:
                            func()
                            sleep(60)
            except Exception as e:
                logger.error(e)

    def scheduler_rnd(self, func, intvl=60, rndmin=0, rndmax=0, CM=None):
        #func:起動する処理
        #intmm:起動間隔（分）
        while True:
            sleep(10)
            try:
                #インターバル分＋流速考慮値
                if rndmin == 0 and rndmax == 0 or rndmin >= rndmax:
                    rndmm = 0
                else:
                    rndmm = random.randint(rndmin,rndmax)
                if CM==None:
                    cmm = 0
                else:
                    cmm = int(CM.get_coolingtime())
                a = (intvl+cmm+rndmm)*60
                logger.info(f'###{func}###  start at : {a}s')
                sleep(a)
                func()
            except Exception as e:
                logger.error(e)


    def start(self):
        self.th.start()
