# coding: utf-8

# config_sample.py -> config.py にファイル名変えてね〜 

# BOTが接続するマストドンサーバ、接続情報（必須）
from pytz import timezone
MASTODON_URL = 'https://example.com'
MASTODON_ACCESS_TOKEN = 'xxxxxxxxx'

# 特殊ユーザID
MASTER_ID = 'your_name'
BOT_ID = 'bot_name'

# Google検索API用key
GOOGLE_KEY = "xxxxxxxxx"
GOOGLE_ENGINE_KEY = "xxxxxxxxx"

# 気象情報配信サーバ（気象庁配信分）
KISHOU_WS = "https://example2.com"
KISHOU_WS_PORT = 10000

# OpenWeather API用のキー
OPENWEATHER_APPID = "xxxxxxxxx"

# 設定値
TIMEZONE_STR = 'Asia/Tokyo'
TIMEZONE = timezone(TIMEZONE_STR)
LOG_LEVEL = 'DEBUG'  # DEBUG,INFO,WARN,ERROR,CRITICAL

# 各種データ置き場
MEDIA_PATH = 'media/'
BOT_LIST_PATH = 'data/.botlist'  # BOTフラグ未設定のBOTがいた場合、手動で追加して無視するようにするためのリスト
KAOMOJI_PATH = 'data/.kaomoji'
KORA_PATH = 'data/.kora'  # 怒られたときの顔文字
NADE_PATH = 'data/.nadelist'
HINPINED_WORDS_PATH = "data/.hintPinto_words"
WATCH_LIST_PATH = 'data/.watch_list'
NO_BOTTLE_PATH = 'data/.no_bottle'
RECIPE_Z_PATH = 'data/recipe_zairyos.txt'
RECIPE_A_PATH = 'data/recipe_amounts.txt'
STATUSES_DB_PATH = "data/statuses.db"
DB_SCHEMA_PATH = "sql/statuses.sql"
EMOJI_PATH = "data/.emoji"
# IPADIC_PATH = "/usr/local/lib/mecab/dic/mecab-ipadic-neologd/"  # mac
IPADIC_PATH = "/usr/lib/x86_64-linux-gnu/mecab/dic/mecab-ipadic-neologd/"  # ubuntu
NAME_DIC_PATH = "data/name.dic"
ID_DIC_PATH = "data/id.dic"
NICODIC_PATH = "data/nicodic.dic"
SIRITORI_DIC_PATH = 'data/siritori.csv'
CITY_LATLOC_PATH = 'data/city_latloc.json'
TWOTWO_DIC_PATH = 'data/twotwo.dic'
NG_WORDS_PATH = 'data/.ng_words'
BOTTLEMAIL_DB_PATH = "data/bottlemail.db"
BOTTLEMAIL_SCHEMA_PATH = "sql/bottlemail.sql"
LOG_PATH = "log/kiribo.log"
