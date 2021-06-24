# coding: utf-8

import random,json
import sys,io,re,os
from pytz import timezone
from datetime import datetime, timedelta
from pprint import pprint as pp
from PIL import Image, ImageFont, ImageDraw
from kiribo import util
from kiribo.config import TAROT_DATA_PATH, TAROT_IMG_PATH, TAROT_CHK_PATH, TAROT_IMGMAP_PATH, FONT_PATH, MEDIA_PATH

with open(TAROT_DATA_PATH, 'r') as f:
    tarot_data = json.load(f)

with open(TAROT_IMGMAP_PATH, 'r') as f:
    imgmap = json.load(f)

ORDER = ["総合", "金運", "恋愛", "健康", "仕事", "遊び"]

def tarot_reading():
    return tarot_data[str(random.randrange(len(tarot_data)))]


def get_tarot_image(tarot):
    return os.path.join(TAROT_IMG_PATH, imgmap[tarot['name']])


def tarot_main():
    tarot = tarot_reading()
    text = f"【{tarot['name']}】{'逆位置' if tarot['rev'] else '正位置'}\n"
    text += f"{tarot['txt1']}\n{tarot['txt2'] if len(tarot['txt2'])>0 else ''}\n"
    text += "\n".join([f"{o}：{'☆'*tarot['stars'][o]}" for o in ORDER])
    text += "\n powerd by :@HKSN:"
    return text, tarot


def tarot_check(acct):
    jst_now = datetime.now(timezone('Asia/Tokyo'))
    if os.path.exists(TAROT_CHK_PATH):
        with open(TAROT_CHK_PATH, 'r') as f:
            acct_chk_data = json.load(f)
    else:
        acct_chk_data = {}
    # 1日以上開けないとダメ
    if acct in acct_chk_data and (jst_now.strftime('%Y%m%d') <= datetime.fromisoformat(acct_chk_data[acct]).strftime('%Y%m%d')):
        return False

    acct_chk_data[acct] = jst_now.isoformat()
    with open(TAROT_CHK_PATH, 'w') as f:
        json.dump(acct_chk_data, f, ensure_ascii=False, indent=2)
    return True


def make_tarot_image(tarot, avatar_static):
    img_path = get_tarot_image(tarot)
    tarot_img = Image.open(img_path)
    if tarot['rev']:
        tarot_img = tarot_img.rotate(180)
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

    font = ImageFont.truetype(FONT_PATH, 32)
    draw = ImageDraw.Draw(image)
    draw.text((tarot_img.width + 32, 12), temp_txt,
              fill=(240, 240, 240), font=font)

    font = ImageFont.truetype(FONT_PATH, 22)
    order = ["総合", "金運", "恋愛", "健康", "仕事", "遊び"]
    tarot_txt = f"【{tarot['name']}】{'逆位置' if tarot['rev'] else '正位置'}\n"

    MAXLENGTH = 19
    tarot_txt += f"{tarot['txt1'][:MAXLENGTH]}"
    if len(tarot['txt1']) > MAXLENGTH:
        tarot_txt += '\n'
        tarot_txt += tarot['txt1'][MAXLENGTH:]
    if len(tarot['txt2']) > 0:
        tarot_txt += '\n'
        tarot_txt += f"{tarot['txt2'][:MAXLENGTH]}"
        if len(tarot['txt2']) > MAXLENGTH:
            tarot_txt += '\n'
            tarot_txt += tarot['txt2'][MAXLENGTH:]
    tarot_txt += '\n'
    tarot_txt += "\n".join([f"{o}：{'☆'*tarot['stars'][o]}" for o in order])

    draw.text((tarot_img.width + 12, 56), tarot_txt,
              fill=(240, 240, 240), font=font)

    image.save(os.path.join(MEDIA_PATH, "tarot_tmp.png"))
    return os.path.join(MEDIA_PATH, "tarot_tmp.png")


if __name__ == '__main__':
    avatar_static = "https://kiritan.work/system/accounts/avatars/000/000/001/original/039525c0ca872f5d.png"
    print(tarot_check("kiritan"))
    tarot_txt, tarot = tarot_main()
    print(tarot_txt)
    print(make_tarot_image(tarot, avatar_static))
