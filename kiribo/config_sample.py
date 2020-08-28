# coding: utf-8

# config_sample.py -> config.py にファイル名変えてね〜 

# BOTが接続するマストドンサーバ、接続情報（必須）
MASTODON_URL = 'https://example.com'
MASTODON_CLIENT_ID = 'xxxxxxxxx'
MASTODON_CLIENT_SECRET = 'xxxxxxxxx'
MASTODON_ACCESS_TOKEN = 'xxxxxxxxx'

# 特殊ユーザID
MASTER_ID = 'your_name'
BOT_ID = 'bot_name'

# Google検索API用key
GOOGLE_ENABLE = False
GOOGLE_KEY = "xxxxxxxxx"
GOOGLE_ENGINE_KEY = "xxxxxxxxx"

# 気象情報配信サーバ（気象庁配信分）
KISHOU_ENABLE = False
KISHOU_WS = "https://example2.com"
KISHOU_WS_PORT = 10000

# OpenWeather API用のキー
OPENWEATHER_ENABLE = False
OPENWEATHER_APPID = "xxxxxxxxx"

# ディープラーニング系機能の使用有無
DEEPLEARNING_ENABLE = False