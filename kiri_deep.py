# coding: utf-8

from tensorflow.python.keras.models import load_model
from tensorflow.python.keras import backend
from gensim.models.doc2vec import Doc2Vec
import MeCab
import numpy as np
import random,json
import sys,io,re,gc
from liner import kiri_coloring_model
import kiri_util
from time import sleep
import unicodedata
from PIL import Image, ImageOps, ImageFile, ImageChops, ImageFilter, ImageEnhance
import cv2
import tensorflow as tf
config = tf.ConfigProto(device_count={"GPU":1},
                        gpu_options=tf.GPUOptions(allow_growth=False, visible_device_list="3"))
session = tf.Session(config=config)
backend.set_session(session)

labels = {}
with open('dic/.cnn_labels','r') as f:
    labels_index = json.load(f)
for label,i in labels_index.items():
    labels[i] = label

STANDARD_SIZE = (299, 299)
# STANDARD_SIZE = (512, 512)
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
#変更するとモデル再構築必要
VEC_SIZE = 256  # Doc2vecの出力より
VEC_MAXLEN = 7     # vec推定で参照するトゥート(vecor)数
TXT_MAXLEN = 5      # 
MU = "🧪"       # 無
END = "🦷"      # 終わりマーク
tagger = MeCab.Tagger('-Owakati -d /usr/lib/mecab/dic/mecab-ipadic-neologd -u dic/nicodic.dic')
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

d2v_path = 'db/d2v.model'
# lstm_vec_path = 'db/lstm_vec.h5'
lstm_set_path = 'db/lstm_set.h5'

d2vmodel = Doc2Vec.load(d2v_path)
# lstm_vec_model = load_model(lstm_vec_path)
lstm_set_model = load_model(lstm_set_path)

takomodel_path = 'db/cnn_v1.h5'
takomodel = load_model(takomodel_path)

graph = tf.get_default_graph()


def sample(preds, temperature=1.2):
    # helper function to sample an index from a probability array
    preds = np.asarray(preds).astype('float64')
    preds = np.log(preds) / temperature
    exp_preds = np.exp(preds)
    preds = exp_preds / np.sum(exp_preds)
    probas = np.random.multinomial(1, preds, 1)
    return np.argmax(probas)

def lstm_gentxt(toots,num=0,sel_model=None):
    # 入力トゥート（VEC_MAXLEN）をベクトル化。
    input_vec = np.zeros((1,VEC_MAXLEN, VEC_SIZE))
    if len(toots) >= VEC_MAXLEN:
        toots_nrm = toots[-VEC_MAXLEN:]
    else:
        toots_nrm = toots + [toots[-1]]*(VEC_MAXLEN-len(toots))

    # # 直近のトゥートの色を濃くする（+3分の調整）
    # toots_nrm.append(toots[-2])
    # toots_nrm.append(toots[-1])
    # toots_nrm.append(toots[-1])

    for i,toot in enumerate(toots_nrm):
        wakati = tagger.parse(toot).split(" ")
        input_vec[0,i,:] = d2vmodel.infer_vector(wakati)

    # ベクトル推定（平均値を使う）
    # with graph.as_default():
    #     output_vec = lstm_vec_model.predict_on_batch(input_vec)[0]
    output_vec = np.mean(input_vec, axis=1)
    output_vec = np.reshape(output_vec,(output_vec.shape[1]))

    ret = d2vmodel.docvecs.most_similar([output_vec])
    print("lstm_gen --------------------")
    print("  目標のトゥート")
    for toot_id, score in ret[:4]:
        row = DAO.pickup_1toot(toot_id)
        print(f"{score:2f}:{kiri_util.content_cleanser(row[1])}")

    # 推定したベクトルから文章生成
    generated = ''
    char_IDs = [char_idx[MU] for _ in range(TXT_MAXLEN)]    #初期値は無
    rnd = random.uniform(0.1,0.5)

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
    print(f'gen pre,rnd={rtn_text},{rnd:2f}')
    rtn_text = re.sub(END,'',rtn_text, flags=(re.MULTILINE | re.DOTALL))
    # rtn_text = re.sub(r'。{2,}','。',rtn_text, flags=(re.MULTILINE | re.DOTALL))
    # rtn_text = re.sub(r'^[。、\n]','',rtn_text, flags=(re.MULTILINE | re.DOTALL))
    # rtn_text = rtn_text.strip()
    print(f'gen text,rnd={rtn_text},{rnd:2f}')
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
        # takomodel.load_weights(takomodel_path + 'w', by_name=False)
        result = takomodel.predict(np.array([image/255.0]))

    rslt_dict = {}
    for i,rslt in enumerate(result[0]):
        rslt_dict[labels[i]] = rslt
    print("*** image:", filepath.split('/')[-1])  #, "\n*** result:", rslt_dict)
    for k, v in sorted(rslt_dict.items(), key=lambda x: -x[1])[:4]:
        print('{0}:{1:.2%}'.format(k,v))

    with open('image.log','a') as f:
        f.write("*** image:" + filepath.split('/')[-1] +  "  *** result:%s\n"%str(rslt_dict))
    if max(result[0]) > 0.93:
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
