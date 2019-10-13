# coding: utf-8

from keras.models import load_model, Model
from gensim.models.doc2vec import Doc2Vec
import MeCab
import numpy as np
import random,json
import sys,io,re,gc,os
import kiri_util
from time import sleep
from datetime import datetime,timedelta
from pytz import timezone
import unicodedata
from PIL import Image, ImageOps, ImageFile, ImageChops, ImageFilter, ImageEnhance
import cv2
import tensorflow as tf
# config = tf.ConfigProto(device_count={"GPU":1},
#                         gpu_options=tf.GPUOptions(allow_growth=False, visible_device_list="3"))
# session = tf.Session(config=config)
# backend.set_session(session)

labels = {}
with open('dic/.cnn_labels','r') as f:
    labels_index = json.load(f)
for label,i in labels_index.items():
    labels[i] = label

STANDARD_SIZE = (299, 299)
STANDARD_SIZE_S1 = (128, 128)
STANDARD_SIZE_S2 = (512, 512)

#いろいろなパラメータ
#変更するとモデル再構築必要
VEC_SIZE = 256  # Doc2vecの出力より
VEC_MAXLEN = 10     # vec推定で参照するトゥート(vecor)数
AVE_LEN = 2        # vec推定で平均化する幅
TXT_MAXLEN = 5      # 
MU = "🧪"       # 無
END = "🦷"      # 終わりマーク

tagger = MeCab.Tagger('-Owakati -u dic/nicodic.dic')
DAO = kiri_util.DAO_statuses()

pat3 = re.compile(r'^\n')
pat4 = re.compile(r'\n')

#辞書読み込み
wl_chars = list(open('dic/wl.txt').read())
idx_char = {i:c for i,c in enumerate(wl_chars)}
num_chars = len(idx_char)
idx_char[num_chars] = MU
idx_char[num_chars+1] = END
char_idx = {c:i for i,c in enumerate(wl_chars)}
char_idx[MU] = num_chars
char_idx[END] = num_chars + 1

d2vmodel = Doc2Vec.load('db/d2v.model')
lstm_vec_model = load_model('db/lstm_vec.h5')
lstm_set_model = load_model('db/lstm_set.h5')

takomodel = load_model('db/cnn.h5')

graph = tf.get_default_graph()

def sample(preds, temperature=1.2):
    # helper function to sample an index from a probability array
    preds = np.asarray(preds).astype('float64')
    preds = np.log(preds) / temperature
    exp_preds = np.exp(preds)
    preds = exp_preds / np.sum(exp_preds)
    probas = np.random.multinomial(1, preds, 1)
    return np.argmax(probas)

def lstm_gentxt(toots):
    # 入力トゥート（VEC_MAXLEN）をベクトル化。
    input_vec = np.zeros((VEC_MAXLEN + AVE_LEN, VEC_SIZE))
    input_mean_vec = np.zeros((VEC_MAXLEN, VEC_SIZE))
    temp_toots = [t.strip() for t in toots if len(t.strip()) > 0]
    if len(temp_toots) >= VEC_MAXLEN + AVE_LEN:
        toots_nrm = temp_toots[-(VEC_MAXLEN + AVE_LEN):]
    else:
        toots_nrm = temp_toots + [temp_toots[-1]]*(VEC_MAXLEN + AVE_LEN -len(temp_toots))

    print("lstm_gen --------------------")
    print("  inputトゥート")
    for i,toot in enumerate(toots_nrm):
        print(toot)
        wakati = tagger.parse(toot).split(" ")
        input_vec[i] = d2vmodel.infer_vector(wakati)

    for i in range(VEC_MAXLEN):
        input_mean_vec[i] = np.mean(input_vec[i:i+AVE_LEN], axis=0)

    # ベクトル推定
    input_mean_vec = input_mean_vec.reshape((1,VEC_MAXLEN, VEC_SIZE))
    with graph.as_default():
        output_vec = lstm_vec_model.predict_on_batch(input_mean_vec)[0]

    # 推定したベクトルから文章生成
    generated = ''
    char_IDs = [char_idx[MU] for _ in range(TXT_MAXLEN)]    #初期値は無
    rnd = random.uniform(0.2,0.7)

    for i in range(200):
        with graph.as_default():
            preds = lstm_set_model.predict_on_batch([ np.asarray([output_vec]),  np.asarray([char_IDs]) ])

        next_index = sample(preds[0], rnd)
        char_IDs = char_IDs[1:]
        char_IDs.append(next_index)
        next_char = idx_char[next_index]
        generated += next_char
        if next_char == END:
            break

    rtn_text = generated
    rtn_text = re.sub(END,r'',rtn_text, flags=(re.MULTILINE | re.DOTALL))
    rtn_text = re.sub(r'(.)(.)(.)(.)(.)(.)(\1\2\3\4\5\6){4,}',r'\7\7',rtn_text, flags=(re.MULTILINE | re.DOTALL))
    rtn_text = re.sub(r'(.)(.)(.)(.)(.)(\1\2\3\4\5){4,}',r'\6\6',rtn_text, flags=(re.MULTILINE | re.DOTALL))
    rtn_text = re.sub(r'(.)(.)(.)(.)(\1\2\3\4){4,}',r'\5\5',rtn_text, flags=(re.MULTILINE | re.DOTALL))
    rtn_text = re.sub(r'(.)(.)(.)(\1\2\3){4,}',r'\4\4',rtn_text, flags=(re.MULTILINE | re.DOTALL))
    rtn_text = re.sub(r'(.)(.)(\1\2){4,}',r'\3\3',rtn_text, flags=(re.MULTILINE | re.DOTALL))
    rtn_text = re.sub(r'(.)\1{4,}',r'\1\1',rtn_text, flags=(re.MULTILINE | re.DOTALL))
    print(f'gen text,rnd={rtn_text},{rnd:2f}')
    return rtn_text

def takoramen(filepath):
    extention = filepath.rsplit('.',1)[-1]
    print(filepath,extention)
    if extention in ['png','jpg','jpeg','gif']:
        image = Image.open(filepath)
        image = kiri_util.new_convert(image, "RGB")
        image = image.resize(STANDARD_SIZE) 
        image = np.asarray(image)
    elif extention in ['mp4','webm']:
        cap = cv2.VideoCapture(filepath)
        _, image = cap.read()
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = np.asarray(Image.fromarray(image).resize(STANDARD_SIZE))
    else:
        return 'other'

    with graph.as_default():
        result = takomodel.predict(np.array([image/255.0]))

    rslt_dict = {}
    for i,rslt in enumerate(result[0]):
        rslt_dict[labels[i]] = rslt
    print("*** image:", filepath.split('/')[-1])  #, "\n*** result:", rslt_dict)
    for k, v in sorted(rslt_dict.items(), key=lambda x: -x[1])[:4]:
        print('{0}:{1:.2%}'.format(k,v))

    with open('image.log','a') as f:
        f.write("*** image:" + filepath.split('/')[-1] +  "  *** result:%s\n"%str(rslt_dict))
    if max(result[0]) > 0.8:
        return labels[np.argmax(result[0])]
    else:
        return 'other'

if __name__ == '__main__':
    text = ''
    while text != 'exit':
        print('input path')
        text = input('>>>')
        print(takoramen(text))
