# coding: utf-8

import random,json
import sys,io,re,os
from pytz import timezone
from datetime import datetime, timedelta
from pprint import pprint as pp
from PIL import Image, ImageFont, ImageDraw
from kiribo import util
from kiribo.config import TAROT_DATA_PATH, TAROT_IMG_PATH, TAROT_CHK_PATH, FONT_PATH, MEDIA_PATH

with open(TAROT_DATA_PATH, 'r') as f:
    tarot_data = json.load(f)


def tarot_reading():
    return tarot_data[str(random.randrange(len(tarot_data)))]


def get_tarot_image(tarot):
    return f'{TAROT_IMG_PATH}{tarot["no"]:02}_{"R" if tarot["rev"] else "N"}.png'


def tarot_main():
    order = ["総合", "金運", "恋愛", "健康", "仕事", "遊び"]
    tarot = tarot_reading()
    img_path = get_tarot_image(tarot)
    text = f"【{tarot['name']}】{'逆位置' if tarot['rev'] else '正位置'}\n"
    text += f"{tarot['txt1']}\n{tarot['txt2'] if len(tarot['txt2'])>0 else ''}\n"
    text += "\n".join([f"{o}：{'☆'*tarot['stars'][o]}" for o in order])
    text += "\n powerd by :@HKSN:"
    text += "\n 画像提供 https://www.pixiv.net/artworks/71664018"
    return text, img_path, tarot


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


def make_tarot_image(tarot, img_path, avatar_static):
    tarot_img = Image.open(img_path)
    image = Image.new("RGBA", (tarot_img.width * 3,
                               tarot_img.height), (0, 0, 0, 255))
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
    avatar_static = "https://kiritan.work/system/accounts/avatars/000/000/001/original/cb1e8c8141f59051.png"
    print(tarot_check("kiritan"))
    tarot_txt, img_path, tarot = tarot_main()
    make_tarot_image(tarot, img_path, avatar_static)

'''
{
    "id": "1",
    "username": "kiritan",
    "acct": "kiritan",
    "display_name": "きりたん :taisyou:",
    "locked": false,
    "bot": false,
    "discoverable": true,
    "group": false,
    "created_at": "2018-08-25T10:32:17.160Z",
    "note": "<p>( っ&apos;-&apos;)╮ =͟͟͞͞  :katsu_curry: :kamehameha:<br />( っ&apos;-&apos;)╮ =͟͟͞͞ (  っ˃̵ᴗ˂̵)っ<br />(    ε¦) ﾆｬｧｧｧｧ!<br />( っ&apos;-&apos;)╮ =͟͟͞͞ (˃̵ᴗ˂̵)　ｻｯ!!<br />SW-6356-5322-0040<br />ロビーのパスワードは0120にするのだわい<br />( っ&apos;-&apos;)╮ =͟͟͞͞  :kiribo: &lt;( っ&apos;-&apos;)╮ =͟͟͞͞  :kiribo: &lt;( っ&apos;-&apos;)╮ =͟͟͞͞  :kiribo: &lt;ｳﾜｰﾝ<br />(๑˃́ꇴ˂̀๑)ｷﾞｭｰﾝ!</p>",
    "url": "https://kiritan.work/@kiritan",
    "avatar": "https://kiritan.work/system/accounts/avatars/000/000/001/original/cb1e8c8141f59051.png",
    "avatar_static": "https://kiritan.work/system/accounts/avatars/000/000/001/original/cb1e8c8141f59051.png",  ☆
    "header": "https://kiritan.work/system/accounts/headers/000/000/001/original/9a412ee94bf51db1.png",
    "header_static": "https://kiritan.work/system/accounts/headers/000/000/001/original/9a412ee94bf51db1.png",
    "followers_count": 629,
    "following_count": 640,
    "statuses_count": 115614,
    "last_status_at": "2021-05-03",
    "emojis": [
        {
            "shortcode": "katsu_curry",
            "url": "https://kiritan.work/system/custom_emojis/images/000/019/719/original/a068efc110d0a3ed.png",
            "static_url": "https://kiritan.work/system/custom_emojis/images/000/019/719/static/a068efc110d0a3ed.png",
            "visible_in_picker": true,
            "account_id": null
        },
        {
            "shortcode": "kamehameha",
            "url": "https://kiritan.work/system/custom_emojis/images/000/011/628/original/54b455bf9ab1081a.png",
            "static_url": "https://kiritan.work/system/custom_emojis/images/000/011/628/static/54b455bf9ab1081a.png",
            "visible_in_picker": true,
            "account_id": null
        },
        {
            "shortcode": "kiribo",
            "url": "https://kiritan.work/system/custom_emojis/images/000/009/267/original/e0f46c0d7c02e892.png",
            "static_url": "https://kiritan.work/system/custom_emojis/images/000/009/267/static/e0f46c0d7c02e892.png",
            "visible_in_picker": true,
            "account_id": null
        },
        {
            "shortcode": "taisyou",
            "url": "https://kiritan.work/system/custom_emojis/images/000/046/168/original/02830dd4f97a8436.png",
            "static_url": "https://kiritan.work/system/custom_emojis/images/000/046/168/static/02830dd4f97a8436.png",
            "visible_in_picker": true,
            "account_id": null
        }
    ],
    "fields": [
        {
            "name": "めいすきー",
            "value": "<a href=\"https://misskey.m544.net/@kiritan\" rel=\"me nofollow noopener noreferrer\" target=\"_blank\"><span class=\"invisible\">https://</span><span class=\"\">misskey.m544.net/@kiritan</span><span class=\"invisible\"></span></a>",
            "verified_at": "2019-07-16T05:02:05.076+00:00"
        },
        {
            "name": "フレカフェ",
            "value": "<a href=\"https://friends.cafe/@kiritan\" rel=\"me nofollow noopener noreferrer\" target=\"_blank\"><span class=\"invisible\">https://</span><span class=\"\">friends.cafe/@kiritan</span><span class=\"invisible\"></span></a>",
            "verified_at": "2019-07-15T08:19:18.505+00:00"
        },
        {
            "name": "有象無象丼",
            "value": "<a href=\"https://uzomuzo.work/@kiritan\" rel=\"me nofollow noopener noreferrer\" target=\"_blank\"><span class=\"invisible\">https://</span><span class=\"\">uzomuzo.work/@kiritan</span><span class=\"invisible\"></span></a>",
            "verified_at": "2020-10-15T03:04:13.546+00:00"
        }
    ],
    "profile_emojis": [],
    "all_emojis": [
        {
            "shortcode": "katsu_curry",
            "url": "https://kiritan.work/system/custom_emojis/images/000/019/719/original/a068efc110d0a3ed.png",
            "static_url": "https://kiritan.work/system/custom_emojis/images/000/019/719/static/a068efc110d0a3ed.png",
            "visible_in_picker": true,
            "account_id": null
        },
        {
            "shortcode": "kamehameha",
            "url": "https://kiritan.work/system/custom_emojis/images/000/011/628/original/54b455bf9ab1081a.png",
            "static_url": "https://kiritan.work/system/custom_emojis/images/000/011/628/static/54b455bf9ab1081a.png",
            "visible_in_picker": true,
            "account_id": null
        },
        {
            "shortcode": "kiribo",
            "url": "https://kiritan.work/system/custom_emojis/images/000/009/267/original/e0f46c0d7c02e892.png",
            "static_url": "https://kiritan.work/system/custom_emojis/images/000/009/267/static/e0f46c0d7c02e892.png",
            "visible_in_picker": true,
            "account_id": null
        },
        {
            "shortcode": "taisyou",
            "url": "https://kiritan.work/system/custom_emojis/images/000/046/168/original/02830dd4f97a8436.png",
            "static_url": "https://kiritan.work/system/custom_emojis/images/000/046/168/static/02830dd4f97a8436.png",
            "visible_in_picker": true,
            "account_id": null
        }
    ]
}
'''
