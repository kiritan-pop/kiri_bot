# coding: utf-8

import os
import sqlite3
import random
import re
from pytz import timezone
from dateutil import parser
from datetime import datetime,timedelta
from contextlib import closing
from collections import defaultdict

# きりぼコンフィグ
from kiribo.config import settings

from kiribo import util

#######################################################
class StatusDao:
    MAX_USERS = 30

    def __init__(self, timeout=3, bot_id="kiri_bot"):
        self.timeout = timeout
        self.bot_id = bot_id
        self._initialize_database()


    def _initialize_database(self):
        if not os.path.exists(settings.statuses_db_path):
            with self._get_connection(isolation_level='EXCLUSIVE') as con:
                with open(settings.db_schema_path, "r") as f:
                    con.executescript(f.read())


    def _get_connection(self, isolation_level=None):
        return sqlite3.connect(settings.statuses_db_path, timeout=self.timeout, isolation_level=isolation_level)


    #######################################################
    # 指定された時間内から一人ユーザを選ぶ
    def sample_acct(self):
        with self._get_connection() as con:
            sql = f"SELECT DISTINCT acct FROM statuses WHERE acct <> ? ORDER BY id DESC LIMIT {self.MAX_USERS}"
            acct_list = list({row[0] for row in con.execute(sql, (self.bot_id,))})
        return random.choice(acct_list) if acct_list else None


    #######################################################
    # ｉｄ指定でトゥート内容を返す
    def pickup_1toot(self, status_id):
        with self._get_connection() as con:
            sql = "SELECT acct, content, date, time FROM statuses WHERE id = ?"
            row = con.execute(sql, (status_id,)).fetchone()
        return row


    #######################################################
    # 陣形用５人ピックアップ
    def get_five(self, num=5):
        with self._get_connection() as con:
            sql = "SELECT DISTINCT acct FROM statuses ORDER BY id DESC LIMIT 20"
            acct_list = list({row[0] for row in con.execute(sql)})
        return random.sample(acct_list, min(num, len(acct_list)))


    #######################################################
    # 最初の投稿取得
    def get_user_toots(self, acct, limit=10):
        with self._get_connection() as con:
            sql = """
            SELECT id, content, date, time 
            FROM statuses 
            WHERE acct = ? 
            ORDER BY id ASC 
            LIMIT ?
            """
            rows = con.execute(sql, (acct, limit)).fetchall()
        return rows


    #######################################################
    # 時間指定トゥート取得
    def get_toots_hours(self, hours=1):
        jst_now = datetime.now(timezone("Asia/Tokyo"))
        past_time = jst_now - timedelta(hours=hours)

        ymd = int(past_time.strftime("%Y%m%d"))
        hms = int(past_time.strftime("%H%M%S"))
        ymd2 = int(jst_now.strftime("%Y%m%d"))
        hms2 = int(jst_now.strftime("%H%M%S"))

        with self._get_connection() as con:
            if ymd == ymd2 and hms <= hms2:
                sql = """
                SELECT acct, COUNT(content)
                FROM statuses
                WHERE date = ? AND time BETWEEN ? AND ?
                GROUP BY acct
                """
                params = (ymd, hms, hms2)
            else:
                sql = """
                SELECT acct, COUNT(content)
                FROM statuses
                WHERE (date = ? AND time >= ?)
                OR (date = ? AND time <= ?)
                OR (date > ? AND date < ?)
                GROUP BY acct
                """
                params = (ymd, hms, ymd2, hms2, ymd, ymd2)

            rows = con.execute(sql, params).fetchall()

        return rows


    #######################################################
    # トゥートの保存
    def save_toot(self, status):
        media_attachments = status["media_attachments"]
        mediatext = " ".join(media["url"] for media in media_attachments)

        jst_time = status["created_at"].astimezone(timezone("Asia/Tokyo"))
        tmpdate = jst_time.strftime("%Y%m%d")
        tmptime = jst_time.strftime("%H%M%S")

        data = (
            str(status["id"]),
            tmpdate,
            tmptime,
            status["content"],
            status["account"]["acct"],
            status["account"]["display_name"],
            mediatext,
        )

        insert_sql = """
            INSERT INTO statuses (id, date, time, content, acct, display_name, media_attachments)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """

        try:
            with self._get_connection() as con:
                con.execute(insert_sql, data)
                con.commit()
        except sqlite3.IntegrityError:
            pass  # 重複エントリの無視
        except sqlite3.Error as e:
            util.logger.error(f"Database error: {e}")


    #######################################################
    # 対象の人のh時間以内のトゥート日付を取得
    def get_least_created_at(self, acct, h=3):
        jst_now = datetime.now(timezone("Asia/Tokyo"))
        past_time = jst_now - timedelta(hours=h)

        ymd = int(past_time.strftime("%Y%m%d"))
        hms = int(past_time.strftime("%H%M%S"))
        ymd2 = int(jst_now.strftime("%Y%m%d"))
        hms2 = int(jst_now.strftime("%H%M%S"))

        with self._get_connection() as con:
            if ymd == ymd2 and hms <= hms2:
                sql = """
                SELECT date, time 
                FROM statuses 
                WHERE acct = ? 
                AND date = ? 
                AND time BETWEEN ? AND ?
                ORDER BY id DESC 
                LIMIT 1
                """
                params = (acct, ymd, hms, hms2)
            else:
                sql = """
                SELECT date, time 
                FROM statuses 
                WHERE acct = ?
                AND (
                    (date = ? AND time >= ?) 
                    OR (date = ? AND time <= ?)
                    OR (date > ? AND date < ?)
                )
                ORDER BY id DESC 
                LIMIT 1
                """
                params = (acct, ymd, hms, ymd2, hms2, ymd, ymd2)

            row = con.execute(sql, params).fetchone()

        if row:
            date = f"{row[0]:08d}"
            time = f"{row[1]:06d}"
            ymdhms = f"{date} {time}"
            return parser.parse(ymdhms).astimezone(timezone("Asia/Tokyo"))
        return None


    #######################################################
    # ほくすんポイント
    def hksn_point(self):
        query = "SELECT content FROM statuses WHERE acct = ?"
        results = []

        # データベースから対象のコンテンツを取得
        with self._get_connection() as conn:
            rows = conn.execute(query, ("HKSN",)).fetchall()
            for row in rows:
                txt = row[0]
                if "ほくずんポイント" in txt or "ほくさぎポイント" in txt:
                    txt = util.content_cleanser(txt)
                    results.append(txt)

        # 正規表現によるポイントの集計
        pattern = r":@(\w+): ([+-]?\d+)"
        usr_scores = defaultdict(int)

        for txt in results:
            matches = re.findall(pattern, txt)
            for user, value in matches:
                usr_scores[user] += int(value)

        return usr_scores


    def hksn_point_ranking(self):
        usr_scores = self.hksn_point()
        top10 = list(sorted(usr_scores.items(),
                    key=lambda item: item[1], reverse=True))[:10]
        bottom10 = list(sorted(usr_scores.items(),
                            key=lambda item: item[1], reverse=False))[:10]
        return top10, bottom10


    def hksn_point_user(self, acct):
        usr_scores = self.hksn_point()
        return usr_scores[acct]


if __name__ == '__main__':
    d = StatusDao()
    # print(d.sample_acct())
    
    while True:
        data = input("> ").strip()
        print(d.hksn_point_ranking())
