# -*- coding: utf-8 -*-
import requests
import json
from time import sleep
import re
import os
from datetime import datetime as dt
from PIL import Image, ImageFont, ImageDraw, PngImagePlugin
from cairosvg import svg2png
import unicodedata
import locale
locale.setlocale(locale.LC_TIME, 'ja_JP.UTF-8')

# きりぼコンフィグ
from kiribo.config import MEDIA_PATH, WEATHER_IMAGES, FONT_PATH, WEATHER_AREA, UA
from kiribo.util import logger


def search_area(word):
    # 市区町村名からコード値を取得するやつ
    with open(WEATHER_AREA, "r") as f:
        area = json.load(f)

    class20s = [v for v in area['class20s'].values(
    ) if re.search(r'^' + word, v['name'])]
    # pp(f"{class20s=}")
    if len(class20s) == 0:
        return 9, "NotFound"
    if len(class20s) > 1:
        return 2, [v['name'] for v in class20s]

    class15s = [(k, v) for k, v in area['class15s'].items()
                if k == class20s[0]['parent']]
    # pp(f"{class15s=}")
    class10s = [(k, v) for k, v in area['class10s'].items()
                if k == class15s[0][1]['parent']]
    # pp(f"{class10s=}")
    return 0, (class10s[0][1]['parent'], class10s[0][0])


def get_forecast_data(quary):
    # 取得した生データを返す
    ret_code, message = search_area(quary)
    if ret_code != 0:
        return ret_code, message

    office_code, class10_code = message

    url = f"https://weather.tsukumijima.net/api/forecast"
    forecast = requests.get(
        url, headers={'User-Agent': UA}, params=dict(city=class10_code)).json()
    sleep(1)

    return 0, forecast


def format_text(text):
    if text:
        return re.sub(r"\s", "", text)
    else:
        return None


def svg2png2image(url):
    os.makedirs(WEATHER_IMAGES, exist_ok=True)
    savepath = os.path.join(WEATHER_IMAGES, url.split(
        "/")[-1].split(".")[0] + ".png")
    if not os.path.exists(savepath):
        svg2png(url=url, write_to=savepath, scale=2)
    return Image.open(savepath)


def make_forecast_image(quary):
    retcode, forecast = get_forecast_data(quary)
    if retcode != 0:
        return retcode, forecast

    HEADER_SIZE = 120
    BASE_ROW_SIZE = 32
    BASE_COLUMN_SIZE = 300


    # ヘッダー
    default_font = ImageFont.truetype(FONT_PATH, 24)
    default_color = (240, 240, 240)
    column_header = ["日付", "天気", "風", "波の高さ", "最低気温", "最高気温", "降水確率", "概況"]
    column_header_size = [2, 4, 1, 1, 1, 1, 1, 5]
    total_height = BASE_ROW_SIZE*sum(column_header_size)
    header_image = draw_table(width=HEADER_SIZE, height=total_height,
                              column=column_header, column_size=column_header_size,
                              font=default_font, font_color=default_color)
    image = Image.new(
        "RGBA", (HEADER_SIZE + BASE_COLUMN_SIZE*3, BASE_ROW_SIZE*sum(column_header_size)), (0, 0, 0, 255))

    image.paste(header_image, (0, 0))

    # 天気予報情報
    color_list = [default_color] * 6 + \
        [(80, 80, 240), (240, 80, 80)] + [default_color] * 2
    font_list = [default_font] * 5 + \
        [ImageFont.truetype(FONT_PATH, 16)] + [default_font] * 4

    for i, fc in enumerate(forecast['forecasts']):
        column_image = draw_table(
            width=BASE_COLUMN_SIZE,
            height=total_height,
            column=[dt.strptime(fc['date'], '%Y-%m-%d').strftime('%-m月%-d日'),
                    fc['dateLabel'],
                    svg2png2image(fc['image']['url']),
                    fc['telop'],
                    fc['detail']['wind'],
                    format_text(fc['detail']['wave']),
                    fc['temperature']['min']['celsius'],
                    fc['temperature']['max']['celsius'],
                    list(fc['chanceOfRain'].values()),
                    ""],
            column_size=[1, 1, 3, 1, 1, 1, 1, 1, 1, 5],
            font=font_list, font_color=color_list)

        image.paste(column_image, (HEADER_SIZE + BASE_COLUMN_SIZE*i, 0))

    # 概況
    overview_text = forecast['description']['text']
    overview_text = format_text(overview_text)
    overview_image = Image.new(
        "RGBA", (BASE_COLUMN_SIZE*len(forecast['forecasts']), BASE_ROW_SIZE*5), (0, 0, 0, 255))
    overview_draw = ImageDraw.Draw(overview_image)
    font = ImageFont.truetype(FONT_PATH, 18)
    MAXLEN = 55
    wrap_list = text_wrap(overview_text, 48)
    for i, wrap_text in enumerate(wrap_list):
        overview_draw.text((2, (font.size + 2)*i+2), wrap_text,
                           font=font, fill=default_color)
    overview_draw.rectangle(
        (0, 0, BASE_COLUMN_SIZE *
         len(forecast['forecasts'])-1, BASE_ROW_SIZE*5-1),
        outline=default_color)
    image.paste(overview_image, (HEADER_SIZE,
                                 total_height - overview_image.height))

    # タイトル
    bg_image = Image.new(
        "RGBA", (HEADER_SIZE + BASE_COLUMN_SIZE*3, BASE_ROW_SIZE*sum(column_header_size)+32), (0, 0, 0, 255))
    title_draw = ImageDraw.Draw(bg_image)
    title = format_text(forecast['title'])
    str_dt = dt.strptime(forecast["publicTime"],
                        '%Y-%m-%dT%H:%M:%S%z').strftime('%-d日%-H時')
    office = forecast["publishingOffice"]
    title = f"{title}（{office} {str_dt} 発表）"
    title_draw.text(((bg_image.width - len_text_eaw(title)*default_font.size)//2, 4), title,
                    font=default_font, fill=default_color)
    bg_image.paste(image, (0, 32))

    file_path = os.path.join(MEDIA_PATH, "tmp_weather.png")
    bg_image.save(file_path)
    return 0, file_path


def text_wrap(text, width=70):
    wrap_list = []
    tmp_text = text
    while True:
        if len(tmp_text) < width:
            wrap_list.append(tmp_text)
            break
        if tmp_text[width] in "」』）｝】＞≫］ぁぃぅぇぉっゃゅょァィゥェォッャュョー―-、。,.ゝ々！？：；／":
            wrap_list.append(tmp_text[:width-1])
            tmp_text = tmp_text[width-1:]
        else:
            wrap_list.append(tmp_text[:width])
            tmp_text = tmp_text[width:]

    return wrap_list


def len_text_eaw(text):
    count = 0
    for c in text:
        if unicodedata.east_asian_width(c) in 'FWA':
            count += 2
        else:
            count += 1
    return count/2


def draw_table(
    width: int,
    height: int,
    column: list,
    column_size: int or list,
    font=None,
    font_color=None,
    line_color=None,
    line_width: int = 1,
):
    NULL_CHAR = "--"
    image = Image.new(
        "RGBA", (width, height), (0, 0, 0, 255))
    draw = ImageDraw.Draw(image)
    if type(column_size) == list:
        if len(column) == len(column_size):
            column_size_px = [h*height//sum(column_size) for h in column_size]
        else:
            raise ValueError("len(column) と len(column_size) が異なる")
    else:
        column_size_px = [column_size for _ in range(len(column))]

    if type(font_color) == list:
        if len(column) == len(font_color):
            font_colors_list = font_color
        else:
            raise ValueError("len(column) と len(font_color) が異なる")
    else:
        font_colors_list = [font_color for _ in range(len(column))]

    if type(font) == list:
        if len(column) == len(font):
            font_list = font
        else:
            raise ValueError("len(column) と len(font) が異なる")
    else:
        font_list = [font for _ in range(len(column))]

    tmp_height = 0
    img_clear = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw.line((0, 0, 0, height), fill=line_color, width=line_width)
    for col, col_size, font_color, font in zip(column, column_size_px, font_colors_list, font_list):
        draw.line((0, tmp_height, width, tmp_height),
                  fill=line_color, width=line_width)
        if type(col) == PngImagePlugin.PngImageFile:
            img_clear.paste(col, ((width - col.width)//2,
                                  tmp_height + (col_size - col.height)//2))
        elif type(col) == list:
            for i, sub_col in enumerate(col):
                draw.text((width//len(col)*i + (width//len(col) - font.size*len_text_eaw(sub_col))/2,
                           tmp_height + col_size//2 - font.size//2), sub_col, font=font, fill=font_color)
                draw.line((width//len(col)*i, tmp_height, width//len(col)*i, tmp_height + col_size),
                          fill=line_color, width=line_width)
        elif type(col) == str:
            draw.text(((width - font.size*len_text_eaw(col))/2, tmp_height + col_size//2 - font.size//2), col,
                      font=font, fill=font_color)
        else:
            draw.text(((width - font.size*len_text_eaw(NULL_CHAR))/2, tmp_height + col_size//2 - font.size//2), NULL_CHAR,
                      font=font, fill=font_color)

        tmp_height += col_size

    draw.line((0, height - line_width, width, height - line_width),
              fill=line_color, width=line_width)
    draw.line((width - line_width, 0, width - line_width, height),
              fill=line_color, width=line_width)

    image = Image.alpha_composite(image, img_clear)
    return image


if __name__ == '__main__':
    print(make_forecast_image("尾道"))
