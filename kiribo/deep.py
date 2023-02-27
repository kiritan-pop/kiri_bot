# coding: utf-8

import logging
import tensorflow as tf
import numpy as np
import json
import re,os
from PIL import Image
import cv2
import shutil

# きりぼコンフィグ
from kiribo import imaging

logger = logging.getLogger(__name__)

# 画像判定用ラベル
labels = {}
with open('data/cnn/.cnn_labels','r') as f:
    labels_index = json.load(f)
for label,i in labels_index.items():
    labels[i] = label

STANDARD_SIZE = (480, 480)

#いろいろなパラメータ
pat3 = re.compile(r'^\n')
pat4 = re.compile(r'\n')

# モデル作成
def build_cnn_model(labels):
    input_image = tf.keras.layers.Input(shape=(480, 480, 3))
    input = tf.keras.layers.GaussianNoise(0.1)(input_image)
    input = tf.keras.layers.RandomFlip()(input)
    # input = tf.keras.layers.RandomCrop(480, 480)(input)
    input = tf.keras.layers.RandomZoom(0.2)(input)
    input = tf.keras.layers.RandomContrast(0.2)(input)
    input = tf.keras.layers.RandomRotation(0.5)(input)
    input = tf.keras.layers.RandomTranslation(0.2, 0.2)(input)

    base_model = tf.keras.applications.efficientnet_v2.EfficientNetV2M(
        input_tensor=input, include_top=False, weights='imagenet')

    x = base_model.output
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dense(512, activation="relu")(x)
    x = tf.keras.layers.Dropout(0.3)(x)
    pred = tf.keras.layers.Dense(len(labels), activation="softmax")(x)

    model = tf.keras.models.Model(inputs=input_image, outputs=pred)

    return model


takomodel = build_cnn_model(labels)
# モデルを読み込む
latest = tf.train.latest_checkpoint(os.path.dirname('data/cnn/checkpoints/cnn.model'))
if latest:
    print(f'*** load model-weights {latest} ***')
    takomodel.load_weights(latest)


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

    result = takomodel.predict(image[np.newaxis, ...])

    rslt_dict = {}
    for i,rslt in enumerate(result[0]):
        rslt_dict[labels[i]] = rslt
    logger.debug(f"*** image:{filepath.split('/')[-1]}")
    for k, v in sorted(rslt_dict.items(), key=lambda x: -x[1])[:4]:
        logger.debug(f"{k}:{v:.2%}")

    with open(os.path.join('log', 'image.log'), 'a') as f:
        f.write("*** image:" + filepath.split('/')[-1] +  "  *** result:%s\n"%str(rslt_dict))
    if max(result[0]) > 0.65:
        savepath = os.path.join("media4ml", labels[np.argmax(result[0])], os.path.basename(filepath))
        os.makedirs(os.path.dirname(savepath), exist_ok=True)
        shutil.copy(filepath, savepath)

    if max(result[0]) > 0.85:
        return labels[np.argmax(result[0])]
    else:
        return 'other'




if __name__ == '__main__':
    pass
