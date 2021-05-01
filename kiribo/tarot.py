# coding: utf-8

import random,json
import sys,io,re,os
from pytz import timezone
from datetime import datetime, timedelta
from pprint import pprint as pp
from kiribo.config import TAROT_DATA_PATH, TAROT_IMG_PATH, TAROT_CHK_PATH

# https://www.pixiv.net/artworks/71664018

with open(TAROT_DATA_PATH, 'r') as f:
    tarot_data = json.load(f)

def tarot_reading():
    return tarot_data[str(random.randrange(len(tarot_data)))]

def get_tarot_image(tarot):
    return f'{TAROT_IMG_PATH}{tarot["no"]:02}_{"R" if tarot["rev"] else "N"}.png'

def tarot_main():
    order = ["総合","金運","恋愛","健康","仕事","遊び"]
    tarot = tarot_reading()
    img_path = get_tarot_image(tarot)
    text = f"【{tarot['name']}】{'逆位置' if tarot['rev'] else '正位置'}\n"
    text += f"{tarot['txt1']}\n{tarot['txt2'] if len(tarot['txt2'])>0 else ''}\n"
    text += "\n".join([f"{o}：{'☆'*tarot['stars'][o]}" for o in order])
    text += "\n powerd by :@HKSN:"
    text += "\n 画像提供 https://www.pixiv.net/artworks/71664018"
    return text, img_path

def tarot_check(acct):
    jst_now = datetime.now(timezone('Asia/Tokyo'))
    if os.path.exists(TAROT_CHK_PATH):
        with open(TAROT_CHK_PATH, 'r') as f:
            acct_chk_data = json.load(f)
    else:
        acct_chk_data = {}
    # 1日以上開けないとダメ
    if acct in acct_chk_data and (jst_now.strftime('%Y%m%d') <= datetime.fromisoformat(acct_chk_data[acct]).strftime('%Y%m%d') ):
        return False

    acct_chk_data[acct] = jst_now.isoformat()
    with open(TAROT_CHK_PATH, 'w') as f:
        json.dump(acct_chk_data, f, ensure_ascii=False, indent=2)
    return True


if __name__ == '__main__':
    print(tarot_check("kiritan"))
    a,b = tarot_main()
    print(a)
    print(type(a))
    print(b)
    print(type(b))

'''
{'name': '力',
 'no': 8,
 'rev': False,
 'stars': {'仕事': 4, '健康': 3, '恋愛': 3, '総合': 4, '遊び': 4, '金運': 3},
 'txt1': '能力や才能をフルに活かせそう',
 'txt2': '色々と成功も見えてくる日だよ～'}

'''
