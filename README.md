# きりぼっと
マストドン（主にニコフレ）のBOTだよー！

## kiri_main.py
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

## kiri_deep.py
lstmによる文章自動生成機能と画像認識だよー！
ユーティリティのlstm_modelingtrain.pyで学習したモデルを使用するよー！

## kiri_util.py
もともとメインにあった処理を細かい機能を分離したよー！

## kiri_game.py
数取りゲームー！

## ranging_dairy3.rb
ランキング機能だよー！rubyの「clockwork」っていうgemで動かすよー！
