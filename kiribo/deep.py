# coding: utf-8

import logging
from onnxruntime import InferenceSession
import unicodedata
from fugashi import Tagger
import numpy as np
import json
import re,os
from PIL import Image
import cv2
import shutil

# きりぼコンフィグ
from kiribo import imaging

logger = logging.getLogger(__name__)

# 画像判定
IMAGE_TYPE = ["jpg", "jpeg", "jpe", "png", "gif", "webp", "bmp"]
session = InferenceSession("data/imgclsfy/model.onnx")

with open("data/imgclsfy/id2label.json", "r") as f:
    id2label = json.load(f)
id2label = {int(k):unicodedata.normalize("NFKC", v) for k,v in id2label.items()}
IMAGE_SIZE = (384, 384)

def sigmoid(x):
    return 1 / (1 + np.exp(-x))

#いろいろなパラメータ
tagger = Tagger(f"-Owakati")
tagger2 = Tagger()

pat3 = re.compile(r'^\n')
pat4 = re.compile(r'\n')


def takoramen(filepath):
    logger.debug(f"{filepath}")
    extention = filepath.rsplit('.',1)[-1].lower()
    if extention in IMAGE_TYPE:
        image = Image.open(filepath)
        image = imaging.new_convert(image, "RGB")
        image = image.resize(IMAGE_SIZE) 
        image = np.asarray(image)
    elif extention in ['mp4','webm']:
        cap = cv2.VideoCapture(filepath)
        _, image = cap.read()
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = np.asarray(Image.fromarray(image).resize(IMAGE_SIZE))
    else:
        return []

    inputs_data = np.transpose(np.array(image),(2,0,1))
    inputs_data = inputs_data[np.newaxis,:]
    inputs_data = np.ascontiguousarray(inputs_data)
    inputs_data = inputs_data/255.0
    inputs_data = inputs_data.astype(np.float32)

    outputs = session.run(None,{'input.1':inputs_data})[0]
    pred = sigmoid(outputs)
    pred_labels =[id2label[id] for id in  list(np.argwhere(pred[0]>=0.65)[:,0])]

    if pred_labels:
        savepath = os.path.join("media4ml", pred_labels[0], os.path.basename(filepath))
        os.makedirs(os.path.dirname(savepath), exist_ok=True)
        shutil.copy(filepath, savepath)

    return pred_labels


if __name__ == '__main__':
    pass
