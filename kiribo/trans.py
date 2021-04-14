# coding: utf-8

import json
import requests

import kiribo.util
logger = kiribo.util.setup_logger(__name__)

class Trans:
    def __init__(self, key):
        self.key = key
        self.url="https://translation.googleapis.com/language/translate/v2"

    def xx2ja(self,lang, text):
        url = self.url
        url += "?key=" + self.key
        url += "&q=" + text
        url += f"&source={lang}&target=ja"
        #
        return self.__req_dec(url)

    def ja2en(self,text):
        url = self.url
        url += "?key=" + self.key
        url += "&q=" + text
        url += f"&source=ja&target=en"
        #
        return self.__req_dec(url)

    def detect(self,text):
        url = self.url +  "/detect"
        url += "?key=" + self.key
        url += "&q=" + text
        rr=requests.get(url)
        unit_aa=json.loads(rr.text)
        try:
            result = unit_aa["data"]["detections"][0][0]["language"]
            return result
        except Exception as e:
            logger.error(e)
            logger.error(result)
            return None

    def __req_dec(self,url):
        rr=requests.get(url)
        unit_aa=json.loads(rr.text)
        try:
            result = unit_aa["data"]["translations"][0]["translatedText"]
            return result
        except Exception as e:
            logger.error(e)
            logger.error(result)
            return None
