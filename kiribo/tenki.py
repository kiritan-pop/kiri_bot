# -*- coding: utf-8 -*-
import os
import requests
import json
from bs4 import BeautifulSoup
from time import sleep
from collections import defaultdict
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import urllib.request
from pytz import timezone
from datetime import datetime, timedelta
from PIL import Image
import locale
locale.setlocale(locale.LC_TIME, 'ja_JP.UTF-8')

# きりぼコンフィグ
import kiribo.util
from kiribo.config import CITY_LATLOC_PATH

ICON_DIR = "tenki_icon"
IMAGE_H = 1260
IMAGE_W = 800
BG_COLOR = "#100500"
LINE_COLOR = "#5f5050"
FONT_COLOR = "#fff5f3"
WEATHER_IMAGE_PATH = "./media"

# 天気メイン
def get_tenki(quary, appid):
    with open(CITY_LATLOC_PATH, 'r') as fr:
        city_latloc_dict = json.load(fr)
    os.makedirs(ICON_DIR, exist_ok=True)

    hit_tdfk = [tdfk for tdfk in city_latloc_dict.keys() if tdfk in quary]
    hit_skcs = []
    hit_lat = 0.0
    hit_loc = 0.0
    if len(hit_tdfk) == 1:
        # 都道府県指定あり
        for k_skcs, latloc in city_latloc_dict[hit_tdfk[0]].items():
            if quary.split(hit_tdfk[0])[-1] in k_skcs:
                hit_skcs.append(hit_tdfk[0] + k_skcs)
                hit_lat = latloc[0]
                hit_loc = latloc[1]
    else:
        # 都道府県指定なし
        for k_tdfk, v in city_latloc_dict.items():
            for k_skcs, latloc in v.items():
                if quary == k_skcs or quary == k_skcs[:-1]:
                    hit_skcs.append(k_tdfk + k_skcs)
                    hit_lat = latloc[0]
                    hit_loc = latloc[1]

    if len(hit_skcs) == 0:
        return 900, None, None, None  # 見つからなかった場合
    elif len(hit_skcs) > 1:
        return 901, None, "、".join(hit_skcs), None  # 複数見つかった場合

    # 天気情報取得
    url = "http://api.openweathermap.org/data/2.5/onecall"
    payload = {
        "lat": hit_lat, "lon": hit_loc,
        "lang": "ja",
                "units": "metric",
                "APPID": appid}
    tenki_data = requests.get(url, params=payload).json()
    tz = timezone(tenki_data['timezone'])
    skcs_name = hit_skcs[0]

    return 0, hit_skcs[0]+"の天気", \
        make_weather_image_current(tenki_data['current'], skcs_name, tz),\
        [make_weather_image_daily(tenki_data['daily'], skcs_name, tz),
        make_weather_image_hourly(tenki_data['hourly'], skcs_name, tz),
        make_weather_image_minutely(tenki_data['minutely'], skcs_name, tz)]


# UV指数
def get_uvi_info(uvi):
    if uvi < 3.0:
        return f"弱い", "rgb(204,242,255)"
    elif uvi < 6.0:
        return f"中程度", "rgb(255,255,204)"
    elif uvi < 8.0:
        return f"強い", "rgb(255,204,153)"
    elif uvi < 11.0:
        return f"非常に強い", "rgb(255,101,101)"
    else:
        return f"極端に強い", "rgb(255,101,255)"


# 現在の天気
def make_weather_image_current(wd, skcs_name, tz):
    tmp_dict = {}
    tmp_dict['曇り％'] = wd['clouds']
    tmp_dict['日時'] = datetime.fromtimestamp(
        wd['dt'], tz=tz).strftime("%m/%d %H:%M")
    tmp_dict['体感気温℃'] = f"{float(wd['feels_like']):.1f}"
    tmp_dict['湿度％'] = wd['humidity']
    tmp_dict['気圧hPa'] = wd['pressure']
    tmp_dict['日の出'] = datetime.fromtimestamp(
        wd['sunrise'], tz=tz).strftime("%H:%M:%S")
    tmp_dict['日の入'] = datetime.fromtimestamp(
        wd['sunset'], tz=tz).strftime("%H:%M:%S")
    tmp_dict['気温℃'] = f"{float(wd['temp']):.1f}"
    uv_text, _ = get_uvi_info(wd['uvi'])
    tmp_dict['UV指数'] = f"{uv_text}({float(wd['uvi']):.1f})"
    tmp_dict['天気'] = wd['weather'][0]['description']

    ret_text = f"現在({tmp_dict['日時']}時点)の{skcs_name}の天気\n"
    ret_text += f"{tmp_dict['天気']}："
    ret_text += f"気温{tmp_dict['気温℃']}℃／湿度{tmp_dict['湿度％']}％／体感気温{tmp_dict['体感気温℃']}℃\n"
    ret_text += f"気圧{tmp_dict['気圧hPa']}hPa／UV指数「{tmp_dict['UV指数']}」／雲率{tmp_dict['曇り％']}％\n"
    ret_text += f"日の出時刻は{tmp_dict['日の出']}、日の入時刻は{tmp_dict['日の入']}\n"
    ret_text += f"　　by OpenWeatherMap API https://openweathermap.org/"

    return ret_text


# １週間天気
def make_weather_image_daily(wd, skcs_name, tz):
    tenki_data_list = []

    for l1 in wd:
        tmp_dict = {}
        tmp_dict['日付'] = datetime.fromtimestamp(
            l1['dt'], tz=tz).strftime("%m/%d(%a)")
        tmp_dict['☀☁'] = ""  # お天気アイコン表示用
        tmp_dict['icon'] = l1['weather'][0]['icon']
        tmp_dict['天気'] = l1['weather'][0]['description']
        tmp_dict['最高気温℃'] = f"{float(l1['temp']['max']):.1f}"
        tmp_dict['最低気温℃'] = f"{float(l1['temp']['min']):.1f}"
        tmp_dict['降水確率％'] = int(float(l1['pop'])*100)
        tmp_dict['UV指数'], tmp_dict['uv_color'] = get_uvi_info(l1['uvi'])
        tmp_dict['font_color'] = FONT_COLOR

        tenki_data_list.append(tmp_dict)

    df_temp = pd.json_normalize(tenki_data_list)
    df = df_temp[['日付', '☀☁', '天気', '最高気温℃', '最低気温℃', '降水確率％', 'UV指数']]  # テーブルの作成
    fig = go.Figure(data=[go.Table(
        columnwidth=[25, 10, 25, 20, 20, 20, 20],  # カラム幅の変更
        header=dict(values=df.columns, align='center', font=dict(color=FONT_COLOR, size=18), height=30,
                    line_color=LINE_COLOR, fill_color=BG_COLOR),
        cells=dict(values=df.values.T, align='center', font=dict(color=[df_temp.font_color]*6 + [df_temp.uv_color], size=18), height=30,
                    line_color=LINE_COLOR, fill_color=BG_COLOR),
        )],
        layout=dict(margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor=BG_COLOR,
                    title=dict(
                        text=skcs_name+"の１週間天気", x=0.5, y=1.0, font=dict(color=FONT_COLOR, size=24), xanchor='center', yanchor='top', pad=dict(l=0, r=0, t=5, b=0))
                    )
    )

    # お天気アイコン貼り付け
    for i in range(1, len(df)+1, 1):
        # 天気アイコン取得
        icon_name = df_temp['icon'][i-1]
        icon_image = get_weather_icon(icon_name)
        fig.add_layout_image(
            dict(source=icon_image, x=0.18, y=(1.0-1.0/(len(df)+1)*(i+0.5))))
    fig.update_layout_images(dict(
        xref="paper", yref="paper", sizex=0.22, sizey=0.21, xanchor="left", yanchor="middle"))

    imagepath = os.path.join(WEATHER_IMAGE_PATH, "tmp_weather_d.png")
    fig.write_image(imagepath, height=30*(len(df)+2), width=800, scale=1)

    return imagepath


# ４８時間天気
def make_weather_image_hourly(wd, skcs_name, tz):
    tenki_data_list = []

    for l1 in wd:
        tmp_dict = {}
        tmp_dict['日時'] = datetime.fromtimestamp(
            l1['dt'], tz=tz).strftime("%m/%d %H時")
        tmp_dict['☀☁'] = ""  # お天気アイコン表示用
        tmp_dict['icon'] = l1['weather'][0]['icon']
        tmp_dict['天気'] = l1['weather'][0]['description']
        tmp_dict['気温℃'] = f"{float(l1['temp']): .1f}"
        tmp_dict['湿度％'] = l1['humidity']
        tmp_dict['体感気温℃'] = f"{float(l1['feels_like']):.1f}"
        tmp_dict['降水確率％'] = int(float(l1['pop'])*100)

        tenki_data_list.append(tmp_dict)

    df_temp = pd.json_normalize(tenki_data_list)
    df = df_temp[['日時', '☀☁', '天気', '気温℃', '湿度％', '体感気温℃', '降水確率％']]  # テーブルの作成
    fig = go.Figure(data=[go.Table(
        # columnorder=[10, 20, 30, 40, 50, 25, 70],
        columnwidth=[25, 10, 25, 20, 20, 20, 20],  # カラム幅の変更
        header=dict(values=df.columns, align='center', font=dict(color=FONT_COLOR, size=18), height=30,
                    line_color=LINE_COLOR, fill_color=BG_COLOR),
        cells=dict(values=df.values.T, align='center', font=dict(color=FONT_COLOR, size=18), height=30,
                    line_color=LINE_COLOR, fill_color=BG_COLOR),
    )],
        layout=dict(margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor=BG_COLOR,
                    title=dict(
                        text=skcs_name+"の４８時間天気", x=0.5, y=1.0, font=dict(color=FONT_COLOR, size=24), xanchor='center', yanchor='top', pad=dict(l=0, r=0, t=5, b=0))
                    ),

    )
    # お天気アイコン貼り付け
    for i in range(1, len(df)+1, 1):
        # 天気アイコン取得
        icon_name = df_temp['icon'][i-1]
        icon_image = get_weather_icon(icon_name)
        fig.add_layout_image(
            dict(source=icon_image, x=0.18, y=(1.0-1.0/49.0*(i+0.5))))
    fig.update_layout_images(dict(
        xref="paper", yref="paper", sizex=0.07, sizey=0.06, xanchor="left", yanchor="middle"))

    imagepath = os.path.join(WEATHER_IMAGE_PATH, "tmp_weather_h.png")
    fig.write_image(imagepath, height=30*(48+2), width=800, scale=1)

    return imagepath


# １時間降水量
def make_weather_image_minutely(wd, skcs_name, tz):
    tenki_data_list = []

    for l1 in wd:
        tmp_dict = {}
        tmp_dict['時刻'] = datetime.fromtimestamp(
            l1['dt'], tz=tz).strftime("%H:%M")
        tmp_dict['降水量mm'] = l1['precipitation']


        tenki_data_list.append(tmp_dict)

    df_temp = pd.json_normalize(tenki_data_list)
    df = df_temp[['時刻', '降水量mm']].round({'降水量mm':2})  # テーブルの作成
    fig = go.Figure([go.Bar(x=df['時刻'], y=df['降水量mm'], text=df['降水量mm'], textposition='auto',
                            marker=dict(color='rgba(150,150,255,0.8)'),
                            y0=0
                            )],
                    layout=dict(margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor=BG_COLOR, plot_bgcolor=BG_COLOR,
                                title=dict(
                                    text=skcs_name+"の１時間の降水量", x=0.5, y=1.0, font=dict(color=FONT_COLOR, size=24), xanchor='center', yanchor='top', pad=dict(l=0, r=0, t=5, b=0)),
                                font=dict(color=FONT_COLOR, size=18),
                                xaxis=dict(title='時刻', showgrid=False),
                                yaxis=dict(title='降水量mm', showgrid=False,
                                rangemode='nonnegative')
                    )
    )

    imagepath = os.path.join(WEATHER_IMAGE_PATH, "tmp_weather_m.png")
    fig.write_image(imagepath, height=400, width=1600, scale=1)

    return imagepath

# 天気アイコン取得
def get_weather_icon(icon_name):
    icon_image_path = os.path.join(ICON_DIR, icon_name + ".png")
    if os.path.exists(icon_image_path):
        pass
    else:
        url = f"http://openweathermap.org/img/wn/{icon_name}@4x.png"
        with urllib.request.urlopen(url) as web_file:
            data = web_file.read()
            with open(icon_image_path, mode='wb') as local_file:
                local_file.write(data)

    return Image.open(icon_image_path)


# テスト
def test():
    url = "http://api.openweathermap.org/data/2.5/forecast"
    payload = {
        "lat": "26.208581", "lon": "127.684452",
        "lang": "ja",
                "units": "metric",
                "APPID": "xxxxxxxx"}
    tenki_data = requests.get(url, params=payload).json()
    pp(tenki_data)
    testpd = pd.json_normalize(tenki_data["list"])
    pp(testpd.columns)
    testpd[["dt_txt", "main.temp_min", "main.temp_max", "rain.3h"]]


if __name__ == '__main__':
    from pprint import pprint as pp
    pp(get_tenki("利尻", "xxxxx"))

