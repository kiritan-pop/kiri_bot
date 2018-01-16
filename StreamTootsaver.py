# -*- coding: utf-8 -*-

import re,sys,json,os,glob
import sqlite3
import time
from pytz import timezone
from dateutil import parser

DB_PATH = "db/statuses.db"

if __name__ == '__main__':

    while True:
        try:
            con = sqlite3.connect(DB_PATH,timeout = 120000)
            c = con.cursor()

            file_list = glob.glob('mq_0001/*.json')
            for filename in file_list:
                f = open(filename, 'r')
                i = 0
                for line in f:
                    # データ整形
                    toot = json.loads(line)
                    if toot['event'] == 'update':
                        status = json.loads(toot['payload'])
                        media_attachments = status["media_attachments"]
                        mediatext = ""
                        for media in media_attachments:
                            mediatext += media["url"] + " "

                        jst_time = parser.parse(status['created_at']).astimezone(timezone('Asia/Tokyo'))
                        fmt = "%Y%m%d"
                        tmpdate = jst_time.strftime(fmt)
                        fmt = "%H%M%S"
                        tmptime = jst_time.strftime(fmt)

                        insert_sql = u"insert into statuses (id, date, time, content, acct, display_name, media_attachments) values (?, ?, ?, ?, ?, ?, ?)"
                        data = (str(status['id']),
                                    tmpdate,
                                    tmptime,
                                    status['content'],
                                    status['account']['acct'],
                                    status['account']['display_name'],
                                    mediatext
                                    )

                        try:
                            con.execute(insert_sql, data)
                        except Exception as e:
                            print(e)
                        if i % 100 == 0:
                            print(data)
                            con.commit()
                        i += 1
                        if not os.path.exists("mq_0002/"):
                            os.mkdir("mq_0002/")
                        os.rename(filename, "mq_0002/" + filename.split('/')[-1])
                f.close()

            # コミットしてクローズ
            con.commit()
            con.close()
            time.sleep(10)
        except Exception as e:
            print(e)
            time.sleep(60)
