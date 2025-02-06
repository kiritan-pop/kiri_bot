# coding: utf-8

import logging
import unicodedata
from fugashi import Tagger
import numpy as np
import json
import re,os
from PIL import Image
import cv2
import shutil

# きりぼコンフィグ
from kiribo.image_classify import predict as image_classify_predict

logger = logging.getLogger(__name__)

# 画像判定
IMAGE_TYPE = ["jpg", "jpeg", "jpe", "png", "gif", "webp", "bmp"]

#いろいろなパラメータ
tagger = Tagger(f"-Owakati")
tagger2 = Tagger()

pat3 = re.compile(r'^\n')
pat4 = re.compile(r'\n')


def takoramen(filepath):
    logger.debug(f"{filepath}")
    extention = filepath.rsplit('.',1)[-1].lower()
    if extention in IMAGE_TYPE:
        image = Image.open(filepath).convert("RGB")
    elif extention in ['mp4','webm']:
        cap = cv2.VideoCapture(filepath)
        _, image = cap.read()
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    else:
        return []

    pred_labels = image_classify_predict(image)

    if pred_labels:
        savepath = os.path.join("media4ml", pred_labels[0], os.path.basename(filepath))
    else:
        savepath = os.path.join("media4ml", "no_category", os.path.basename(filepath))

    os.makedirs(os.path.dirname(savepath), exist_ok=True)
    shutil.copy(filepath, savepath)

    return pred_labels


if __name__ == '__main__':
    print(takoramen("media/1a22cd5eb129a1b6.png"))
