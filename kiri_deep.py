# coding: utf-8

from keras.models import Sequential,load_model
import numpy as np
import random,json
import sys,io,re,gc
import MeCab
from time import sleep
import unicodedata
from PIL import Image
import tensorflow as tf
from keras.backend import tensorflow_backend
#config = tf.ConfigProto(gpu_options=tf.GPUOptions(allow_growth=True, visible_device_list="1"))
config = tf.ConfigProto(device_count={"GPU":0},
                        gpu_options=tf.GPUOptions(allow_growth=True, visible_device_list="1"))
session = tf.Session(config=config)
tensorflow_backend.set_session(session)

labels = {}
with open('.cnn_labels','r') as f:
    labels_index = json.load(f)
for label,i in labels_index.items():
    labels[i] = label

STANDARD_SIZE = (299, 299)

model_path = 'db/lstm_toot_v5.h5'
takomodel_path = 'db/tako4.h5'
print('******* lstm load model %s,%s*******' %(model_path,takomodel_path))
# モデルを読み込む
model = load_model(model_path)
takomodel = load_model(takomodel_path)
graph = tf.get_default_graph()

#いろいろなパラメータ
maxlen = 10           #モデルに合わせて！
diver = 0.5         #ダイバーシティ：大きくすると想起の幅が大きくなるっぽいー！

pat3 = re.compile(r'^\n')
pat4 = re.compile(r'\n')
adaptr = ['だから','それで','しかし','けど','また','さらに',\
        'つまり','さて','そして','で','でね','そんで','でも']
#辞書読み込み
wl_chars = list(open('dic/wl.txt').read())
wl_chars.append(r'\n')
wl_chars.sort()
char_indices = dict((c, i) for i, c in enumerate(wl_chars))
indices_char = dict((i, c) for i, c in enumerate(wl_chars))

def sample(preds, temperature=1.2):
    # helper function to sample an index from a probability array
    preds = np.asarray(preds).astype('float64')
    preds = np.log(preds) / temperature
    exp_preds = np.exp(preds)
    preds = exp_preds / np.sum(exp_preds)
    probas = np.random.multinomial(1, preds, 1)
    return np.argmax(probas)

def lstm_gentxt(text):
    generated = ''
    rnd = random.sample(adaptr, 1)[0]
    tmp = text + '\n' + rnd + '、'

    if len(tmp) > maxlen:
        sentence = tmp[-maxlen:]
    else:
        sentence = tmp * maxlen
        sentence = sentence[-maxlen:]
    print('seed text= %s ' %sentence)
    for i in range(300):
        x_pred = np.zeros((1, maxlen, len(wl_chars)))
        for t, char in enumerate(list(sentence)):
            try:
                x_pred[0, t, char_indices[char]] = 1.
            except:
                #print('error:char=',t,char)
                pass
        with graph.as_default():
            preds = model.predict(x_pred, verbose=0)[0]
        next_index = sample(preds, diver)
        next_char = indices_char[next_index]

        generated += next_char
        sentence = sentence[1:] + next_char
        if generated.count('\n') + generated.count('。') > 2:
            break

    rtn_text = generated
    rtn_text = re.sub(r'。{2,}','。',rtn_text, flags=(re.MULTILINE | re.DOTALL))
    rtn_text = re.sub(r'^。','',rtn_text, flags=(re.MULTILINE | re.DOTALL))
    rtn_text = re.sub(r'^\n','',rtn_text, flags=(re.MULTILINE | re.DOTALL))
    return rtn_text

def takoramen(filepath):
    image = np.asarray(Image.open(filepath).convert('RGB').resize(STANDARD_SIZE) )
    with graph.as_default():
        result = takomodel.predict(np.array([image/255.0]))

    rslt_dict = {}
    for i,rslt in enumerate(result[0]):
        rslt_dict[labels[i]] = '{0:.2%}'.format(rslt)
    print("*** image:", filepath.split('/')[-1], "\n*** result:", rslt_dict)
    with open('image.log','a') as f:
        f.write("*** image:" + filepath.split('/')[-1] +  "  *** result:%s\n"%str(rslt_dict))
    if max(result[0]) > 0.9:
        return labels[np.where(result[0] == max(result[0]) )[0][0]]
    else:
        return 'other'

if __name__ == '__main__':
#    text = ''
#    while text != 'exit':
#        print('input text')
#        text = input('>>>')
#        print(gentxt(text))
    text = ''
    while text != 'exit':
        print('input path')
        text = input('>>>')
        print(takoramen(text))
