# coding: utf-8

from keras.models import load_model, Model
from keras import backend as backend
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
STANDARD_SIZE_S1 = (128, 128)
STANDARD_SIZE_S2 = (512, 512)
# STANDARD_SIZE = (512, 512)

#いろいろなパラメータ
#変更するとモデル再構築必要
VEC_SIZE = 256  # Doc2vecの出力より
VEC_MAXLEN = 10     # vec推定で参照するトゥート(vecor)数
AVE_LEN = 4        # vec推定で参照するトゥート(vecor)数
TXT_MAXLEN = 5      # 
MU = "🧪"       # 無
END = "🦷"      # 終わりマーク
Colors = {}
Colors['red']    = 0
Colors['blue']   = 1
Colors['green']  = 2
Colors['purple'] = 3
Colors['brown']  = 4
Colors['pink']   = 5
Colors['blonde'] = 6
Colors['white']  = 7
Colors['black']  = 8
Colors_rev = {v:k for k,v in Colors.items()}

# 減色
QNUM = 16
color_pallete = np.load("db/color_pallete.npy")

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

d2vmodel = Doc2Vec.load('db/d2v.model')
lstm_vec_model = load_model('db/lstm_vec.h5')
lstm_set_model = load_model('db/lstm_set.h5')

takomodel = load_model('db/cnn.h5')

gens1_model = load_model('db/g_model_s1.h5')
gens2_model = load_model('db/g_model_s2.h5')
colorize_model = Model(
        inputs=[gens1_model.inputs[0], gens1_model.inputs[1], gens2_model.inputs[0]], 
        outputs=[gens2_model([gens2_model.inputs[0], gens1_model.outputs[0]])] )

chino_model = load_model('db/g_chino.h5')

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
    input_vec = np.zeros((VEC_MAXLEN + AVE_LEN, VEC_SIZE))
    input_mean_vec = np.zeros((VEC_MAXLEN, VEC_SIZE))
    if len(toots) >= VEC_MAXLEN + AVE_LEN:
        toots_nrm = toots[-(VEC_MAXLEN + AVE_LEN):]
    else:
        toots_nrm = toots + [toots[-1]]*(VEC_MAXLEN + AVE_LEN -len(toots))

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

    ret = d2vmodel.docvecs.most_similar([output_vec])
    print("  目標のトゥート")
    for toot_id, score in ret[:4]:
        row = DAO.pickup_1toot(toot_id)
        print(f"{score:2f}:{kiri_util.content_cleanser(row[1])}")

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
    print(f'gen pre,rnd={rtn_text},{rnd:2f}')
    rtn_text = re.sub(END,r'',rtn_text, flags=(re.MULTILINE | re.DOTALL))
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
    if max(result[0]) > 0.93:
        return labels[np.argmax(result[0])]
    else:
        return 'other'

def colorize(image_path, color=None):
    img = Image.open(image_path)
    img = kiri_util.new_convert(img, 'L')
    line_image128 =  kiri_util.image_resize(img,STANDARD_SIZE_S1)
    line_image128 = (np.asarray(line_image128)-127.5)/127.5
    line_image128 = np.reshape(line_image128,(1,128,128))
    line_image512 =  kiri_util.image_resize(img,STANDARD_SIZE_S2)
    line_image512 = (np.asarray(line_image512)-127.5)/127.5
    line_image512 = np.reshape(line_image512,(1,512,512))
    if color == None:
        color_num = random.randrange(len(Colors))
    else:
        color_num = color

    r = random.randint(0,9)
    hist = color_pallete[color_num,r]
    hist = np.reshape(hist, (1, QNUM, 4))

    with graph.as_default():
        gen2 = colorize_model.predict([line_image128, hist, line_image512])[0]

    gen2 = (gen2*127.5+127.5).clip(0, 255).astype(np.uint8)

    savepath = 'colorize_images/'
    if not os.path.exists(savepath):
        os.mkdir(savepath)

    tmp = Image.fromarray(gen2)
    tmp = tmp.resize(img.size, Image.LANCZOS )
    tmp = tmp.resize((max(img.size), max(img.size)) ,Image.LANCZOS)
    tmp = kiri_util.crop_center(tmp, img.width, img.height)
    filename = savepath + image_path.split("/")[-1].split(".")[0] + "_" + Colors_rev[color_num] + "_g2.png"
    tmp.save(filename, optimize=True)

    return filename

def make_chino():
    noise = np.random.normal(0.0,1.5,(1,64))
    # noise = np.random.uniform(-1.0,1.0,(1,64))
    with graph.as_default():
        chino_img = chino_model.predict_on_batch(noise)[0]

    chino_img = (chino_img*127.5+127.5).clip(0, 255).astype(np.uint8)

    savepath = 'chino_images/'
    if not os.path.exists(savepath):
        os.mkdir(savepath)

    jst_now = datetime.now(timezone('Asia/Tokyo'))
    jst_now_str = jst_now.strftime("%Y%m%d%H%M%S")
    tmp = Image.fromarray(chino_img)
    filename = savepath + jst_now_str + ".png"
    tmp.save(filename, optimize=True)

    return filename

if __name__ == '__main__':
    text = ''
    while text != 'exit':
        print('input path')
        text = input('>>>')
        print(takoramen(text))
