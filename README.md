# きりぼっと
マストドン（主にニコフレ）のBOTだよー！

## stream.py
メインのプログラムだよー！タイムライン監視、返信を行うよー！
↓はこのプログラムから呼び出されるモジュールだよー！

## PrepareChain.py
マルコフ連鎖による文章作成のためのデータ（sqlite3使用）を作成するよー！

## GenerateText.py
↑で作ったデータを元に文章を自動生成するよー！

## Toot_summary.py
LexRankを使って文章を要約するよー！

## bottlemail.py
ボトルメールサービスの機能だよー！

## lstm_kiri.py
lstmによる文章自動生成機能だよー！
ユーティリティのlstm_modelingtrain.pyで学習したモデルを使用するよー！

## ranging_dairy.rb
ランキング機能だよー！rubyの「clockwork」っていうgemで動かすよー！
