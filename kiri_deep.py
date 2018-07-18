# coding: utf-8

# from keras.models import load_model as keras_load_model
# from keras.backend import tensorflow_backend
from tensorflow.python.keras.models import load_model
from tensorflow.python.keras import backend
from cnn.cnn_model import cnn_model
from lstm.lstm_modelingtrain import lstm_model
import numpy as np
import random,json
import sys,io,re,gc
from liner import kiri_coloring_model
from time import sleep
import unicodedata
from PIL import Image, ImageOps, ImageFile, ImageChops, ImageFilter, ImageEnhance
import cv2
import tensorflow as tf
config = tf.ConfigProto(device_count={"GPU":1},
                        gpu_options=tf.GPUOptions(allow_growth=False, visible_device_list="3"))
session = tf.Session(config=config)
# tensorflow_backend.set_session(session)
backend.set_session(session)

labels = {}
with open('.cnn_labels','r') as f:
    labels_index = json.load(f)
for label,i in labels_index.items():
    labels[i] = label

STANDARD_SIZE = (299, 299)
STANDARD_SIZE2 = (512, 512)
Colors = {}
Colors['red'] = [1,0,0,0,0,0,0,0,0]
Colors['blue'] = [0,1,0,0,0,0,0,0,0]
Colors['green'] = [0,0,1,0,0,0,0,0,0]
Colors['purple'] = [0,0,0,1,0,0,0,0,0]
Colors['brown'] = [0,0,0,0,1,0,0,0,0]
Colors['pink'] = [0,0,0,0,0,1,0,0,0]
Colors['blonde'] = [0,0,0,0,0,0,1,0,0]
Colors['white'] = [0,0,0,0,0,0,0,1,0]
Colors['black'] = [0,0,0,0,0,0,0,0,1]

#いろいろなパラメータ
maxlen = 25           #モデルに合わせて！
diver = 0.55         #ダイバーシティ：大きくすると想起の幅が大きくなるっぽいー！
pat3 = re.compile(r'^\n')
pat4 = re.compile(r'\n')
adaptr = ['だから','それで','しかし','けど','また','さらに',\
        'つまり','さて','そして','で','でね','そんで','でも','ところで','まあ','なるほど','']
#辞書読み込み
wl_chars = list(open('dic/wl.txt').read())
wl_chars.append(r'\n')
wl_chars.sort()
char_indices = dict((c, i) for i, c in enumerate(wl_chars))
indices_char = dict((i, c) for i, c in enumerate(wl_chars))

model_path = 'db/lstm_toot_v4.h5w'
takomodel_path = 'db/cnn_v6.h5w'
# model = keras_load_model(model_path)
# takomodel = load_model(takomodel_path)
model = lstm_model(maxlen, wl_chars)
# model.load_weights(model_path, by_name=False)

takomodel = cnn_model(labels)
# takomodel.load_weights(takomodel_path, by_name=False)

graph = tf.get_default_graph()

# takomodel.save_weights(takomodel_path+'w')


def sample(preds, temperature=1.2):
    # helper function to sample an index from a probability array
    preds = np.asarray(preds).astype('float64')
    preds = np.log(preds) / temperature
    exp_preds = np.exp(preds)
    preds = exp_preds / np.sum(exp_preds)
    probas = np.random.multinomial(1, preds, 1)
    return np.argmax(probas)

def lstm_gentxt(text,num=0,sel_model=None):
    generated = ''
    if sel_model == None:
        tmp_model = model

    rnd = random.choice(adaptr)
    if rnd == '':
        tmp = text
    else:
        tmp = text + '\n' + rnd + '、'

    if len(tmp) > maxlen:
        sentence = tmp[-maxlen:]
    else:
        sentence = tmp * maxlen
        sentence = sentence[-maxlen:]
    print('seed text= %s ' %sentence)
    if num == 0:
        vol = random.randint(1,5)
    else:
        vol = num
    for i in range(300):
        x_pred = np.zeros((1, maxlen, len(wl_chars)))
        for t, char in enumerate(list(sentence)):
            try:
                x_pred[0, t, char_indices[char]] = 1.
            except:
                #print('error:char=',t,char)
                pass
        with graph.as_default():
            model.load_weights(model_path, by_name=False)
            preds = tmp_model.predict(x_pred, verbose=0)[0]
        next_index = sample(preds, diver)
        next_char = indices_char[next_index]

        generated += next_char
        sentence = sentence[1:] + next_char
        if i > 2:
            if generated.count('\n') + generated.count('。') >= vol:
                break

    rtn_text = generated
    rtn_text = re.sub(r'。{2,}','。',rtn_text, flags=(re.MULTILINE | re.DOTALL))
    rtn_text = re.sub(r'^[。、\n]','',rtn_text, flags=(re.MULTILINE | re.DOTALL))
    return rtn_text

def takoramen(filepath):
    extention = filepath.rsplit('.',1)[-1]
    print(filepath,extention)
    if extention in ['png','jpg','jpeg','gif']:
        image = np.asarray(Image.open(filepath).convert('RGB').resize(STANDARD_SIZE) )
    elif extention in ['mp4','webm']:
        cap = cv2.VideoCapture(filepath)
        _, image = cap.read()
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = np.asarray(Image.fromarray(image).resize(STANDARD_SIZE))
    else:
        return 'other'

    with graph.as_default():
        takomodel.load_weights(takomodel_path, by_name=False)
        result = takomodel.predict(np.array([image/255.0]))

    rslt_dict = {}
    for i,rslt in enumerate(result[0]):
        rslt_dict[labels[i]] = rslt
    print("*** image:", filepath.split('/')[-1])  #, "\n*** result:", rslt_dict)
    for k, v in sorted(rslt_dict.items(), key=lambda x: -x[1])[:4]:
        print('{0}:{1:.2%}'.format(k,v))

    with open('image.log','a') as f:
        f.write("*** image:" + filepath.split('/')[-1] +  "  *** result:%s\n"%str(rslt_dict))
    if max(result[0]) > 0.90:
        # return labels[np.where(result[0] == max(result[0]) )[0][0]]
        return labels[np.argmax(result[0])]
    else:
        return 'other'

# def colorize(image_path):
#     img = Image.open(image_path)
#     img = img.convert('RGB')
#     line_image = np.asarray(img)
#     line_size = (line_image.shape[0],line_image.shape[1])
#     img = img.resize(STANDARD_SIZE2,Image.LANCZOS)
#     gray = img.convert("L") #グレイスケール
#     gray2 = gray.filter(ImageFilter.MaxFilter(5))
#     senga_inv = ImageChops.difference(gray, gray2)
#     img = ImageOps.invert(senga_inv)
#     img = img.point(lambda x: 255 if x > 230 else x)
#     img = img.convert("RGB")  #フォーマット戻し
#     img = np.asarray(img)
#     img = (img-127.5)/127.5
#     with graph.as_default():
#         g_model.load_weights(g_model_path, by_name=False)
#         selcol = random.choice(list(Colors.keys()))
#         colorvec = Colors[selcol]
#         image = g_model.predict([np.array([img]), np.array([colorvec]) ])[0]
#         image = (image*127.5+127.5).clip(0, 255).astype(np.uint8)
#         filename = 'media/__coloring.png'
#         Image.fromarray(image).resize((line_size[1],line_size[0]),Image.LANCZOS ).save(filename, optimize=True)
#         return filename

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
