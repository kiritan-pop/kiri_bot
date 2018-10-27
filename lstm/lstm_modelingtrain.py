# coding: utf-8

from tensorflow.python.keras.models import Sequential,load_model
from tensorflow.python.keras.callbacks import LambdaCallback,EarlyStopping
from tensorflow.python.keras.layers import Dense, Activation, CuDNNLSTM, Dropout #, Embedding, Conv1D, MaxPooling1D, Flatten, Input
from tensorflow.python.keras.optimizers import RMSprop
from tensorflow.python.keras.utils import Sequence, multi_gpu_model
from tensorflow.python.keras import backend

import multiprocessing
import numpy as np
import random,json
import sys,io,re,os
from time import sleep
import argparse

import tensorflow as tf

graph = tf.get_default_graph()

#変更するとモデル再構築必要
maxlen = 50
# GPUs = 1

#いろいろなパラメータ
epochs = 10000
# 同時実行プロセス数
process_count = multiprocessing.cpu_count() - 1

def lstm_model(maxlen, wl_chars):
    model = Sequential()
    # model.add(CuDNNLSTM(512, input_shape=(maxlen, len(wl_chars)), return_sequences=True, return_state=True, stateful=True))
    model.add(CuDNNLSTM(1024, return_sequences=True, input_shape=(maxlen, len(wl_chars))))
    model.add(Dropout(0.2))
    model.add(CuDNNLSTM(256, return_sequences=True))
    model.add(Dropout(0.2))
    model.add(CuDNNLSTM(128, return_sequences=True))
    model.add(Dropout(0.2))
    model.add(CuDNNLSTM(64))
    model.add(Dropout(0.2))
    model.add(Dense(len(wl_chars), activation='softmax'))
    return model

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str)
    parser.add_argument("--model_path", type=str)
    parser.add_argument("--gpu", type=str, default='1')
    parser.add_argument("--idx", type=int, default=0)
    parser.add_argument("--batch_size", type=int, default=256)
    args = parser.parse_args()
    return args


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
        self.text = list(open(text_path).read())
        self.batch_size = batch_size
        self.maxlen = maxlen
        deta_len = len(self.text) - maxlen - 1
        self.sample_per_epoch = int(deta_len/self.batch_size)  #端数は切り捨て。端数分は・・・
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
            for t, char in enumerate(sentence):
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
        print()
        print('----- Generating text after Epoch')

        start_index = random.randint(0, len(self.text) - self.maxlen - 1)
        for diversity in [0.25, 0.5, 0.75, 1.0]:
            print()
            print('----- diversity:', diversity)

            generated = ''
            sentence = self.text[start_index: start_index + self.maxlen]
            print('----- Generating with seed: "' + ''.join(sentence) + '"')
            sys.stdout.write(generated)

            for i in range(50):
                #print('debug1 i=%d' %i)
                x_pred = np.zeros((1, self.maxlen, len(self.wl_chars)))
                for t, char in enumerate(sentence):
                    try:
                        x_pred[0, t, self.char_indices[char]] = 1.
                    except:
                        print('error:char=',t,char)
                #print('debug2 x_pred=',x_pred)
                with graph.as_default():
                    preds = model.predict(x_pred, verbose=0)[0]
                next_index = sample(preds, diversity)
                #print('debug3 next_index=',next_index)
                next_char = self.indices_char[next_index]

                generated += next_char
                sentence = sentence[1:]
                sentence.append(next_char)
                sys.stdout.write(next_char)
                sys.stdout.flush()
        print()


def on_epoch_end(epoch, logs):
    ### save
    print('----- saving model...')
    model.save_weights(args.model_path + 'w')
    model.save(args.model_path)

if __name__ == '__main__':
    #パラメータ取得
    args = get_args()
    #GPU設定
    config = tf.ConfigProto(gpu_options=tf.GPUOptions(allow_growth=False,
                                                      visible_device_list=args.gpu
                                                      ))
    session = tf.Session(config=config)
    backend.set_session(session)

    GPUs = len(args.gpu.split(','))

    #辞書読み込み
    wl_chars = list(open('wl.txt').read())
    # wl_chars = list(open('../dic/wl.txt').read())
    wl_chars.append(r'\n')
    wl_chars.sort()
    p_model = None

    model = lstm_model(maxlen, wl_chars)
    model.summary()
    if os.path.exists(args.model_path):
        # loading the model
        print('load model...')
        # model = load_model(sys.argv[2])
        model.load_weights(args.model_path, by_name=False)

    model.compile(loss='categorical_crossentropy', optimizer=RMSprop())
    m = model
    if GPUs > 1:
        p_model = multi_gpu_model(model, gpus=GPUs)
        p_model.compile(loss='categorical_crossentropy', optimizer=RMSprop())
        m = p_model

    start_idx = args.idx
    batch_size = args.batch_size
    generator = TextGenerator(args.input, batch_size, maxlen, wl_chars)
    print_callback = LambdaCallback(on_epoch_end=on_epoch_end)
    ES = EarlyStopping(monitor='loss', min_delta=0.001, patience=10, verbose=0, mode='auto')

    m.fit_generator(generator,
                    callbacks=[print_callback,ES],
                    epochs=epochs,
                    verbose=1,
                    # steps_per_epoch=60,
                    initial_epoch=start_idx,
                    max_queue_size=process_count,
                    workers=4,
                    use_multiprocessing=True)
