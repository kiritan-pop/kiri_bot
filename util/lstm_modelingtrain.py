# coding: utf-8

from __future__ import print_function
from keras.models import Sequential,load_model
from keras.callbacks import LambdaCallback
from keras.layers import Dense, Activation, LSTM, Embedding, Conv1D, MaxPooling1D, Dropout, Flatten, Input
from keras.optimizers import RMSprop
from keras.utils.data_utils import get_file
from keras.utils import Sequence
from keras.utils.training_utils import multi_gpu_model
import multiprocessing
import numpy as np
import random,json
import sys,io,re,os
from time import sleep

import tensorflow as tf
from keras.backend import tensorflow_backend
config = tf.ConfigProto(gpu_options=tf.GPUOptions(allow_growth=True, visible_device_list="0"))
session = tf.Session(config=config)
tensorflow_backend.set_session(session)
graph = tf.get_default_graph()

#変更するとモデル再構築必要
maxlen = 20
GPUs = 1

#いろいろなパラメータ
batch_size = (1024+1024+1024+1024)*GPUs     #大きくすると精度が上がるけど、モデル更新が遅くなるよー！
epochs = 10         #トレーニングの回数
# 同時実行プロセス数
process_count = multiprocessing.cpu_count() - 1

def sample(preds, temperature=1.0):
    # helper function to sample an index from a probability array
    preds = np.asarray(preds).astype('float64')
    preds = np.log(preds) / temperature
    exp_preds = np.exp(preds)
    preds = exp_preds / np.sum(exp_preds)
    probas = np.random.multinomial(1, preds, 1)
    return np.argmax(probas)

class TextGenerator(Sequence):
    def __init__(self, text_path, batch_size, maxlen, wl_chars):
        # コンストラクタ
        self.text = open(text_path).read()
        self.batch_size = batch_size
        self.maxlen = maxlen
        self.deta_len = len(self.text) - maxlen - 1
        self.sample_per_epoch = int(self.deta_len/self.batch_size)  #端数は切り捨て。端数分は・・・
        self.wl_chars = wl_chars
        self.char_indices = dict((c, i) for i, c in enumerate(self.wl_chars))
        self.indices_char = dict((i, c) for i, c in enumerate(self.wl_chars))

    def __getitem__(self, idx):
        # データの取得実装
        sentences = []
        next_chars = []

        for i in range(self.batch_size*idx,self.batch_size*(idx+1)):
            try:
                sentences.append(self.text[i: i + self.maxlen])
                next_chars.append(self.text[i + self.maxlen])
            except:
                break

        x = np.zeros((len(sentences), self.maxlen, len(self.wl_chars)), dtype=np.bool)
        y = np.zeros((len(sentences), len(self.wl_chars)), dtype=np.bool)

        for i, (sentence,next_char) in enumerate(zip(sentences,next_chars)):
            for t, char in enumerate(list(sentence)):
                try:
                    x[i, t, self.char_indices[char]] = 1
                except:
                    continue
            try:
                y[i, self.char_indices[next_char]] = 1
            except:
                continue

        return x, y

    def __len__(self):
        # 全データ数をバッチサイズで割って、何バッチになるか返すよー！
        return self.sample_per_epoch

    def on_epoch_end(self):
        # Function invoked at end of each epoch. Prints generated text.
        ### save
        print('----- saving model...')
        with graph.as_default():
            model.save(sys.argv[2])
            print()
            print('----- Generating text after Epoch')

            start_index = random.randint(0, len(self.text) - self.maxlen - 1)
            for diversity in [0.2, 0.5, 1.0, 1.2]:
                print()
                print('----- diversity:', diversity)

                generated = ''
                sentence = self.text[start_index: start_index + self.maxlen]
                print('----- Generating with seed: "' + sentence + '"')
                sys.stdout.write(generated)

                for i in range(50):
                    #print('debug1 i=%d' %i)
                    x_pred = np.zeros((1, self.maxlen, len(self.wl_chars)))
                    for t, char in enumerate(list(sentence)):
                        try:
                            x_pred[0, t, self.char_indices[char]] = 1.
                        except:
                            print('error:char=',t,char)
                    #print('debug2 x_pred=',x_pred)
                    preds = model.predict(x_pred, verbose=0)[0]
                    next_index = sample(preds, diversity)
                    #print('debug3 next_index=',next_index)
                    next_char = self.indices_char[next_index]

                    generated += next_char
                    sentence = sentence[1:] + next_char

                    sys.stdout.write(next_char)
                    sys.stdout.flush()
        print()

if __name__ == '__main__':
    #辞書読み込み
    wl_chars = list(open('../dic/wl2.txt').read())
    wl_chars.append(r'\n')
    wl_chars.sort()

    if len(sys.argv) < 3:
        print('パラメータ足りないよ！')
        quit()
    if os.path.exists(sys.argv[2]):
        # loading the model
        print('load model...')
        model = load_model(sys.argv[2])
    else:
        # build the model: a single LSTM
        print('Build model...')
        model = Sequential()
        model.add(LSTM(512, return_sequences=True, input_shape=(maxlen, len(wl_chars))))  #4096
        model.add(Dropout(0.1))
        model.add(LSTM(256, return_sequences=True))
        model.add(Dropout(0.1))
        model.add(LSTM(128))
        model.add(Dropout(0.1))
        model.add(Dense(len(wl_chars)))
        model.add(Activation('softmax'))

        if GPUs > 1:
            model = multi_gpu_model(model, gpus=GPUs)

        optimizer = RMSprop()
        model.compile(loss='categorical_crossentropy', optimizer=optimizer)

    model.summary()

    start_idx = 0
    if len(sys.argv) == 4 :
        if sys.argv[3].isdigit():
            start_idx = int(sys.argv[3])

    #print_callback = LambdaCallback(on_epoch_end=on_epoch_end)
    generator = TextGenerator(sys.argv[1], batch_size, maxlen, wl_chars)
    with graph.as_default():
        model.fit_generator(generator,
                            epochs=epochs,
                            #callbacks=[print_callback],
                            verbose=1,
                            #validation_data=None,
                            #validation_steps=None,
                            #class_weight=None,
                            initial_epoch=start_idx,
                            max_queue_size=process_count * 5,
                            workers=process_count,
                            use_multiprocessing=True)
