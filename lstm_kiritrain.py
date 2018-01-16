# coding: utf-8

from keras.models import Sequential,load_model
import numpy as np
import random,json
import sys,io,re,gc
import MeCab
from time import sleep
import unicodedata
import tensorflow as tf
from keras.backend import tensorflow_backend
config = tf.ConfigProto(gpu_options=tf.GPUOptions(allow_growth=True, visible_device_list="1"))
#config = tf.ConfigProto(gpu_options=tf.GPUOptions(allow_growth=True))
session = tf.Session(config=config)
tensorflow_backend.set_session(session)

model_path = 'db/tootmodel10.h5'

#いろいろなパラメータ
batch_size = 256     #大きくすると精度が上がるけど、モデル更新が遅くなるよー！
maxlen = 30         #
step = 3            #
epochs = 30         #トレーニングの回数
diver = 0.1         #ダイバーシティ：大きくすると想起の幅が大きくなるっぽいー！

#tagger = MeCab.Tagger('-Owakati -d /usr/lib/mecab/dic/mecab-ipadic-neologd -u dic/name.dic,dic/id.dic,dic/nicodic.dic')
pat3 = re.compile(r'^\n')
pat4 = re.compile(r'\n')
#辞書読み込み
wl_chars = list(open('dic/wl.txt').read())
wl_chars.append(r'\n')
wl_chars.sort()
char_indices = dict((c, i) for i, c in enumerate(wl_chars))
indices_char = dict((i, c) for i, c in enumerate(wl_chars))


class Lstm_kiritrain():
    def __init__(self):
        print('---lstm load model ')
        self.model = load_model(model_path)

    def train(self, text):
        # cut the text in semi-redundant sequences of maxlen characters
        sentences = []
        next_char = []
        for i in range(0, len(text) - maxlen, step):
            sentences.append(text[i: i + maxlen])
            next_char.append(text[i + maxlen])
        x = np.zeros((len(sentences), maxlen, len(wl_chars)), dtype=np.bool)
        y = np.zeros((len(sentences), len(wl_chars)), dtype=np.bool)
        for i, sentence in enumerate(sentences):
            for t, char in enumerate(list(sentence)):
                try:
                    x[i, t, char_indices[char]] = 1
                except:
                    continue
            try:
                y[i, char_indices[next_char[i]]] = 1
            except:
                continue

        # train the model
        self.model.fit(x, y,
                  batch_size=batch_size,
                  epochs=epochs)
        ### save
        self.model.save(model_path)


if __name__ == '__main__':
    lk = Lstm_kiri()
    text = ''
    while text != 'exit':
        print('input text')
        text = input('>>>')
        print(lk.gentxt(text))
