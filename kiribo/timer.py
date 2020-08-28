# coding: utf-8

import threading
from time import sleep


#######################################################
# きりたんタイマー
class Timer():
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