# coding: utf-8

from tensorflow.keras.models import load_model
import MeCab
import numpy as np
import json
import re,os
from PIL import Image
import cv2

# きりぼコンフィグ
from kiribo.config import NICODIC_PATH, IPADIC_PATH
from kiribo import imaging, util
logger = util.setup_logger(__name__)

# 画像判定用ラベル
labels = {}
with open('data/.cnn_labels','r') as f:
    labels_index = json.load(f)
for label,i in labels_index.items():
    labels[i] = label

STANDARD_SIZE = (299, 299)
STANDARD_SIZE_S1 = (128, 128)
STANDARD_SIZE_S2 = (512, 512)

#いろいろなパラメータ
#変更するとモデル再構築必要
DOC_VEC_SIZE = 32  # Doc2vecの出力より
VEC_MAXLEN = 10     # vec推定で参照するトゥート(vecor)数
AVE_LEN = 2        # vec推定で平均化する幅
TXT_MAXLEN = 5      # 
MU = "🧪"       # 無
END = "🦷"      # 終わりマーク

tagger = MeCab.Tagger(f"-Owakati -u {NICODIC_PATH} -d {IPADIC_PATH}")

pat3 = re.compile(r'^\n')
pat4 = re.compile(r'\n')

takomodel = load_model('data/cnn.h5')


def takoramen(filepath):
    logger.debug(f"{filepath}")
    extention = filepath.rsplit('.',1)[-1]
    if extention in ['png','jpg','jpeg','gif']:
        image = Image.open(filepath)
        image = imaging.new_convert(image, "RGB")
        image = image.resize(STANDARD_SIZE) 
        image = np.asarray(image)
    elif extention in ['mp4','webm']:
        cap = cv2.VideoCapture(filepath)
        _, image = cap.read()
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = np.asarray(Image.fromarray(image).resize(STANDARD_SIZE))
    else:
        return 'other'

    result = takomodel.predict(np.array([image/255.0]))

    rslt_dict = {}
    for i,rslt in enumerate(result[0]):
        rslt_dict[labels[i]] = rslt
    logger.debug(f"*** image:{filepath.split('/')[-1]}")
    for k, v in sorted(rslt_dict.items(), key=lambda x: -x[1])[:4]:
        logger.debug(f"{k}:{v:.2%}")

    with open(os.path.join('log', 'image.log'), 'a') as f:
        f.write("*** image:" + filepath.split('/')[-1] +  "  *** result:%s\n"%str(rslt_dict))
    if max(result[0]) > 0.8:
        return labels[np.argmax(result[0])]
    else:
        return 'other'

if __name__ == '__main__':
    pass
