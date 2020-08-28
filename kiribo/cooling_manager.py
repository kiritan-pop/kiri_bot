# coding: utf-8

import threading
from pytz import timezone
from time import sleep

from kiribo import util
logger = util.setup_logger(__name__)


#######################################################
# クーリングタイム管理
class CoolingManager():
    def __init__(self,base_time=10):
        self.base_time = base_time
        self.created_ats = []
        threading.Thread(target=self.timer_showflowrate).start()

    def count(self,created_at):
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
            logger.info(f"***流速:{self._flowrate():.1f}toots/分")

    def get_coolingtime(self):
        return self._flowrate() * self.base_time / 60
