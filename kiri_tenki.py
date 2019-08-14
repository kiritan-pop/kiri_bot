# -*- coding: utf-8 -*-
from pprint import pprint as pp
import requests
import json
from time import sleep


def get_tenki(quary,day="今日"):
    with open('area_code.json', 'r') as fr:
        area_code_dict = json.load(fr)

    hit_area = {}
    for code, area_data in area_code_dict.items():
        # 市区町村名がピッタリマッチしたらそれで行く
        if quary == area_data['city'] or sum([1 for pin in area_data['pinpoint'] if quary == pin]) > 0:
            hit_area = {}
            hit_area[code] = area_data['city']
            break
        # ざっくりヒットした場合は候補であれする
        if quary in area_data['area'] or quary in area_data['city'] or quary in area_data['prefecture'] or sum([1 for pin in area_data['pinpoint'] if quary in pin]) > 0:
            hit_area[code] = area_data['city']

    if len(hit_area) == 0:
        return "900", "見つからなかったー"
    elif len(hit_area) > 1:
        return "901", "、".join(hit_area.values())

    url = "http://weather.livedoor.com/forecast/webservice/json/v1"
    payload = {"city": list(hit_area.keys())[0]}
    sleep(1)
    tenki_data = requests.get(url, params=payload).json()
    _d = {"今日": 0, "明日": 1, "明後日": 2}
    if day not in ["今日", "明日", "明後日"]:
        day = "今日"

    tenki_data_day = tenki_data['forecasts'][_d[day]]
    tenki_icon_num = tenki_data_day['image']['url'].split("/")[-1].split(".")[0]
    if tenki_data_day['temperature']['max']:
        tenki_temp_max = f"{tenki_data_day['temperature']['max']['celsius']}℃"
    else:
        tenki_temp_max = "--℃"

    if tenki_data_day['temperature']['min']:
        tenki_temp_min = f"{tenki_data_day['temperature']['min']['celsius']}℃"
    else:
        tenki_temp_min = "--℃"

    title = f"{tenki_data['title']} {tenki_data_day['dateLabel']}({tenki_data_day['date']}):tenki{tenki_icon_num}:{tenki_data_day['telop']}（気温{tenki_temp_max}/{tenki_temp_min}）"
    rettxt = f"■{tenki_data['title']}\n"
    rettxt += f" {tenki_data_day['dateLabel']}({tenki_data_day['date']})の天気は:tenki{tenki_icon_num}:{tenki_data_day['telop']}（気温{tenki_temp_max}/{tenki_temp_min}）でしょう。\n"
    rettxt += "\n".join([l for l in tenki_data['description']['text'].split("\n") if len(l)>0 ]) + "\n"
    rettxt += f"\nfrom livedoor 天気情報(http://weather.livedoor.com/)"

    return title,rettxt

if __name__ == '__main__':
    area, day, *_ = input(">地域名 今日/明日/明後日＝").split(" ")
    title,txt = get_tenki(area, day)
    print(title)
    print(txt)

