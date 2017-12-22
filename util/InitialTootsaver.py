# -*- coding: utf-8 -*-

import re,sys,json
import sqlite3
import time
from pytz import timezone
from dateutil import parser

DB_PATH = "db/statuses.db"

if __name__ == '__main__':

    con = sqlite3.connect(DB_PATH)
    c = con.cursor()
    create_table = '''
    drop table if exists statuses;
    create table statuses (
        id integer primary key not null,
        date integer not null,
        time integer not null,
        content text,
        acct text,
        display_name text,
        media_attachments text
    );
    create index date_idx on statuses(date);
    create index time_idx on statuses(time);
    create index datetime_idx on statuses(date,time);
    '''
    c.executescript(create_table)

    f = open('./mq_0011/04base.txt','r')
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
            if i % 10000 == 0:
                print(data)
                #分割コミット
                con.commit()
            i += 1

    # コミットしてクローズ
    con.commit()
    con.close()
    f.close()
