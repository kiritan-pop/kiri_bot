# coding: utf-8

import random,json
import sys,io,re,os
from pytz import timezone
from datetime import datetime, timedelta
from pprint import pprint as pp
from PIL import Image, ImageFont, ImageDraw
from kiribo import util
from kiribo.config import settings

import requests


with open(settings.tarot_april_data_path, 'r') as f:
    tarot_data = json.load(f)
 
def tarot_reading():
    return random.sample(tarot_data, 1)[0]


def get_tarot_image(tarot):
    return os.path.join(settings.tarot_april_img_path, f"{tarot['name']}.jpg")


def tarot_main():
    tarot = tarot_reading()
    print(f"{tarot=}")
    text = f"【{tarot['name']}】\n"
    text += f"{tarot['txt1']}\n"
    text += "\n".join([f"{k}：{'☆'*v}" for k, v in tarot['stars'].items()])
    return text, tarot


def make_tarot_image(tarot, avatar_static):
    img_path = get_tarot_image(tarot)
    tarot_img = Image.open(img_path)
    # 画像のアスペクト比を維持しつつリサイズする
    tarot_img.thumbnail((184, 320))
    
    # 画像の中央からクロップする領域を計算
    width, height = tarot_img.size
    left = (width - 184) / 2
    top = (height - 320) / 2
    right = (width + 184) / 2
    bottom = (height + 320) / 2
    
    # 画像をクロップする
    tarot_img = tarot_img.crop((left, top, right, bottom))

    image = Image.new("RGBA", (640, 320), (0, 0, 0, 255))
    image.paste(tarot_img, (0, 0))

    avatar_static_img_path = util.download_media(avatar_static)
    # アイコン
    if avatar_static_img_path:
        avatar_static_img = Image.open(avatar_static_img_path).convert("RGB")
        max_size = max(avatar_static_img.width, avatar_static_img.height)
        RS_SIZE = 36
        avatar_static_img = avatar_static_img.resize(
            (avatar_static_img.width*RS_SIZE//max_size, avatar_static_img.height*RS_SIZE//max_size), resample=Image.LANCZOS)
        image.paste(avatar_static_img, (tarot_img.width + 72, 8))

    # 文字追加
    jst_now = datetime.now(timezone('Asia/Tokyo'))
    temp_txt = f"　　　{int(jst_now.strftime('%m'))}月{int(jst_now.strftime('%d'))}日の運勢"

    font = ImageFont.truetype(settings.font_path, 32)
    draw = ImageDraw.Draw(image)
    draw.text((tarot_img.width + 32, 12), temp_txt,
              fill=(240, 240, 240), font=font)

    font = ImageFont.truetype(settings.font_path, 22)
    tarot_txt = f"【{tarot['name']}】\n"

    MAXLENGTH = 19
    tarot_txt += f"{tarot['txt1'][:MAXLENGTH]}"
    if len(tarot['txt1']) > MAXLENGTH:
        tarot_txt += '\n'
        tarot_txt += tarot['txt1'][MAXLENGTH:]

    tarot_txt += '\n\n'
    tarot_txt += "\n".join([f"{k}：{'☆'*v}" for k, v in tarot['stars'].items()])

    draw.text((tarot_img.width + 12, 56), tarot_txt,
              fill=(240, 240, 240), font=font)

    image.save(os.path.join(settings.media_path, "tarot_april_tmp.png"))
    return os.path.join(settings.media_path, "tarot_april_tmp.png")


