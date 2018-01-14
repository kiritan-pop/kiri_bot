# coding: utf-8

from keras.models import Sequential,load_model
import numpy as np
import random,json
import sys,io,re
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
print('******* lstm load model %s*******' %model_path)
model = load_model(model_path)

#いろいろなパラメータ
batch_size = 256     #大きくすると精度が上がるけど、モデル更新が遅くなるよー！
bunkatu = 100       #インプットファイルを分割！メモリ足りないので
maxlen = 30         #
step = 3            #
epochs = 50         #トレーニングの回数
diver = 0.4         #ダイバーシティ：大きくすると想起の幅が大きくなるっぽいー！

#tagger = MeCab.Tagger('-Owakati -d /usr/lib/mecab/dic/mecab-ipadic-neologd -u dic/name.dic,dic/id.dic,dic/nicodic.dic')
pat3 = re.compile(r'^\n')
pat4 = re.compile(r'\n')
#辞書読み込み
wl_chars = list(open('dic/wl.txt').read())
wl_chars.append(r'\n')
wl_chars.sort()
char_indices = dict((c, i) for i, c in enumerate(wl_chars))
indices_char = dict((i, c) for i, c in enumerate(wl_chars))


class Lstm_kiri():
    def __init__(self):
        pass

    def sample(self, preds, temperature=1.2):
        # helper function to sample an index from a probability array
        preds = np.asarray(preds).astype('float64')
        preds = np.log(preds) / temperature
        exp_preds = np.exp(preds)
        preds = exp_preds / np.sum(exp_preds)
        probas = np.random.multinomial(1, preds, 1)
        return np.argmax(probas)

    def train(self, text):
        print('---lstm load model ')
        model = load_model(model_path)
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
        model.fit(x, y,
                  batch_size=batch_size,
                  epochs=epochs)
        ### save
        model.save(model_path)

    def gentxt(self, text):
        generated = ''
        sentence = text[-maxlen:]
        #print('input text= %s ' %text)
        print('seed text= %s ' %sentence)
        for i in range(100):
            x_pred = np.zeros((1, maxlen, len(wl_chars)))
            for t, char in enumerate(list(sentence)):
                try:
                    x_pred[0, t, char_indices[char]] = 1.
                except:
                    print('error:char=',t,char)
            preds = model.predict(x_pred, verbose=0)[0]
            next_index = self.sample(preds, diver)
            next_char = indices_char[next_index]

            generated += next_char
            sentence = sentence[1:] + next_char
            if generated.count('\n') > 3:
                break

        rtn_text = '。'.join(generated.split('\n')) + '。'
        rtn_text = re.sub(r'。+','。',rtn_text)
        return rtn_text

if __name__ == '__main__':
    lk = Lstm_kiri()
    text = ''
    while text != 'exit':
        print('input text')
        text = input('>>>')
        print(lk.gentxt(text))
