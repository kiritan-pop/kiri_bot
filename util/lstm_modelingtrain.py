# coding: utf-8

'''Example script to generate text from Nietzsche's writings.
At least 20 epochs are required before the generated text
starts sounding coherent.
It is recommended to run this script on GPU, as recurrent
networks are quite computationally intensive.
If you try this script on new data, make sure your corpus
has at least ~100k characters. ~1M is better.
'''

from __future__ import print_function
from keras.models import Sequential,load_model
from keras.callbacks import LambdaCallback
from keras.layers import Dense, Activation, LSTM, Embedding, Conv1D, MaxPooling1D, Dropout, Flatten, Input
from keras.optimizers import RMSprop
from keras.utils.data_utils import get_file
from keras.utils import Sequence
from keras.utils.training_utils import multi_gpu_model
import numpy as np
import random,json
import sys,io,re,os
from time import sleep

import tensorflow as tf
from keras.backend import tensorflow_backend
config = tf.ConfigProto(gpu_options=tf.GPUOptions(visible_device_list="0"))
#config = tf.ConfigProto(gpu_options=tf.GPUOptions(allow_growth=True))
session = tf.Session(config=config)
tensorflow_backend.set_session(session)

#変更するとモデル再構築必要
maxlen = 30
step = 3
GPUs = 1

#いろいろなパラメータ
batch_size = 512     #大きくすると精度が上がるけど、モデル更新が遅くなるよー！
bunkatu = 3000       #インプットファイルを分割！メモリ足りないので
epochs = 30          #トレーニングの回数


def sample(preds, temperature=1.0):
    # helper function to sample an index from a probability array
    preds = np.asarray(preds).astype('float64')
    preds = np.log(preds) / temperature
    exp_preds = np.exp(preds)
    preds = exp_preds / np.sum(exp_preds)
    probas = np.random.multinomial(1, preds, 1)
    return np.argmax(probas)

def on_epoch_end(epoch, logs):
    # Function invoked at end of each epoch. Prints generated text.
    ### save
    print()
    print('----- Generating text after Epoch: %d' % epoch)
    with open('lstm_log.txt','a') as fo:
        fo.write(str(logs))
    print('----- saving model...')
    model.save(sys.argv[2])

    start_index = random.randint(0, len(text) - maxlen - 1)
    for diversity in [0.2, 0.5, 1.0, 1.2]:
        print()
        print('----- diversity:', diversity)

        generated = ''
        sentence = text[start_index: start_index + maxlen]
        print('----- Generating with seed: "' + sentence + '"')
        sys.stdout.write(generated)

        for i in range(50):
            #print('debug1 i=%d' %i)
            x_pred = np.zeros((1, maxlen, len(wl_chars)))
            for t, char in enumerate(list(sentence)):
                try:
                    x_pred[0, t, char_indices[char]] = 1.
                except:
                    print('error:char=',t,char)
            #print('debug2 x_pred=',x_pred)
            preds = model.predict(x_pred, verbose=0)[0]
            next_index = sample(preds, diversity)
            #print('debug3 next_index=',next_index)
            next_char = indices_char[next_index]

            generated += next_char
            sentence = sentence[1:] + next_char

            sys.stdout.write(next_char)
            sys.stdout.flush()
            with open('lstm_text.txt','a') as fo:
                fo.write("epoch:%d diversity:%.1f\n '%s'\n\n" %(epoch,diversity,generated))

    print()

if __name__ == '__main__':
    #辞書読み込み
    wl_chars = list(open('wl.txt').read())
    wl_chars.append(r'\n')
    wl_chars.sort()
    char_indices = dict((c, i) for i, c in enumerate(wl_chars))
    indices_char = dict((i, c) for i, c in enumerate(wl_chars))
    print('wl_chars:', len(wl_chars))

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
        model.add(LSTM(2048, return_sequences=True, input_shape=(maxlen, len(wl_chars))))
        model.add(Dropout(0.2))
        model.add(LSTM(512, return_sequences=True))
        model.add(Dropout(0.2))
        model.add(LSTM(256))
        model.add(Dropout(0.2))
        model.add(Dense(len(wl_chars)))
        model.add(Activation('softmax'))

        if GPUs > 1:
            model = multi_gpu_model(model, gpus=GPUs)

        optimizer = RMSprop()
        model.compile(loss='categorical_crossentropy', optimizer=optimizer)

    print_callback = LambdaCallback(on_epoch_end=on_epoch_end)
    model.summary()

    if len(sys.argv) <= 3 :
        start_idx = 0
    else:
        if sys.argv[3].isdigit():
            start_idx = int(sys.argv[3])
        else:
            start_idx = 0

    for xxx in range(start_idx,bunkatu):
        print('----- Total itr %d/%d' %(xxx,bunkatu))
        chars = []
        for i,line in enumerate(open(sys.argv[1])):
            if int(i/10000 ) % bunkatu == xxx:   #n件毎まとめたいので！
                for char in line.strip()+'\n':
                    if char in wl_chars:
                        chars.append(char)
        text = ''.join(chars)
        del chars
        print('corpus length:',len(text))

        # cut the text in semi-redundant sequences of maxlen characters
        sentences = []
        next_char = []
        for i in range(0, len(text) - maxlen, step):
            sentences.append(text[i: i + maxlen])
            next_char.append(text[i + maxlen])
        print('nb sequences:', len(sentences))

        print('Vectorization...')
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

        del sentences
        del next_char
        print('x.shape:',x.shape)
        print('y.shape:',y.shape)
        # train the model, output generated text after each iteration
        print('Model fitting...')
        model.fit(x, y,
                  batch_size=batch_size,
                  epochs=epochs,
                  #validation_split=0.01,
                  callbacks=[print_callback])
