# coding: utf-8

import os
import numpy as np
import cv2
import requests
from PIL import Image, ImageOps, ImageFile, ImageChops, ImageFilter, ImageEnhance
ImageFile.LOAD_TRUNCATED_IMAGES = True

from kiribo import util
logger = util.setup_logger(__name__)

def face_search(image_path):
    try:
        #HAAR分類器の顔検出用の特徴量
        # cascade_path = "haarcascades/haarcascade_frontalface_default.xml"
        # cascade_path = "haarcascades/haarcascade_frontalface_alt.xml"
        # cascade_path = "haarcascades/haarcascade_frontalface_alt2.xml"
        cascade_path = "haarcascades/haarcascade_frontalface_alt_tree.xml"

        color = ( 5, 5, 200) #赤
        #color = (0, 0, 0) #黒

        #ファイル読み込み
        image = cv2.imread(image_path)

        #カスケード分類器の特徴量を取得する
        cascade = cv2.CascadeClassifier(cascade_path)

        #物体認識（顔認識）の実行
        #image – CV_8U 型の行列．ここに格納されている画像中から物体が検出されます
        #objects – 矩形を要素とするベクトル．それぞれの矩形は，検出した物体を含みます
        #scaleFactor – 各画像スケールにおける縮小量を表します
        #minNeighbors – 物体候補となる矩形は，最低でもこの数だけの近傍矩形を含む必要があります
        #flags – このパラメータは，新しいカスケードでは利用されません．古いカスケードに対しては，cvHaarDetectObjects 関数の場合と同じ意味を持ちます
        #minSize – 物体が取り得る最小サイズ．これよりも小さい物体は無視されます
        facerect = cascade.detectMultiScale(image, scaleFactor=1.1, minNeighbors=1, minSize=(48, 48))

        logger.debug(f"face rectangle {facerect}")

        if len(facerect) > 0:
            #検出した顔を囲む矩形の作成
            for rect in facerect:
                cv2.rectangle(image, tuple(rect[0:2]),tuple(rect[0:2]+rect[2:4]), color, thickness=3)

            #認識結果の保存
            # save_path = ('media/detected.jpg')
            save_path = 'media/' + image_path.rsplit('/',1)[-1].split('.')[0] + '_face.jpg'
            logger.debug(f"save_path = {save_path}")

            cv2.imwrite(save_path, image)
            return save_path
        else:
            return None
    except Exception as e:
        logger.error(e)
        return None


def newyear_icon_maker(path, mode=0):
    logger.info("newyear_icon_maker")
    REP = 1
    if mode==0:
        STEP = 2
        DWON = 4
        cap = cv2.VideoCapture("data/material/newyear.mp4")
    elif mode==1:
        STEP = 2
        DWON = 2
        cap = cv2.VideoCapture("data/material/gear.mp4")
    elif mode==2:
        STEP = 1
        DWON = 3
        REP = 2
        cap = cv2.VideoCapture("data/material/nc178379.mp4")

    FPS = 30//STEP

    base_images = []
    anime_images = []
    cnt = 0
    if path.split(".")[-1].lower() not in ('jpg', 'jpeg', 'gif', 'png', 'bmp'):
        return None

    base_icon = Image.open(path)
    logger.info(f"mode={base_icon.mode}")
    if base_icon.mode in ["RGB", "L", "P"]:
        newpath = auto_alpha(path)
        base_icon = Image.open(newpath)
    elif base_icon.mode == "RGBA":
        tmp = np.asarray(base_icon.split()[3])
        # ほとんど透過していない場合も
        if np.mean(tmp) >= 250:
            newpath = auto_alpha(path)
            base_icon = Image.open(newpath)

    base_icon = base_icon.convert("RGBA")

    SIZE = (base_icon.width*400//max(base_icon.size),
            base_icon.height*400//max(base_icon.size))
    base_icon = base_icon.resize(SIZE, Image.LANCZOS)

    def dwondwon(x):
        if x < 0:
            return 0
        elif x > 1:
            return dwondwon(x - 1.0)
        
        if x <= 0.2:
            return x/0.2
        else:
            return 1.0 - (x-0.2)/0.8

    for _ in range(REP):
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        while True:
            flag, img = cap.read()
            if flag == False:
                break
            if cnt % STEP == 0:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(img)  #.resize(SIZE, Image.LANCZOS)
                if max(img.size) > 500:
                    img = crop_center(img, 500, 500)
                base_images.append(img)
            cnt += 1

    for i, base_image in enumerate(base_images):
        if base_icon.mode == "RGBA":
            tmp = base_icon.copy()
            # 横揺れ
            rate = 5 * np.sin(2.0*np.pi*i/len(base_images))
            tmp = tmp.rotate(rate, expand=True, resample=Image.BICUBIC)

            # ドゥンドゥン
            rate = 1.0 + 0.15 * dwondwon(DWON*i/len(base_images))
            tmp = tmp.resize((int(tmp.width*rate), int(tmp.height*rate)),
                             resample=Image.BICUBIC)

            base_image.paste(tmp, ((base_image.width - tmp.width)//2,
                                   base_image.height - tmp.height), mask=tmp.split()[3])
        else:
            return None

        anime_images.append(base_image.resize((400,400), Image.LANCZOS).convert("P", dither=None,
                            palette=Image.ADAPTIVE, colors=256))

    genpath = path.split(".")[0] + "_gen.gif"
    anime_images[0].save(genpath,
                         # save_all=True, append_images=anime_images[1:], include_color_table=True, interlace=True, optimize=True, duration=1000.0/(30.0*STEP), loop=0)
                         save_all=True, append_images=anime_images[1:], optimize=True, duration=1000.0/FPS, loop=0)

    return genpath


def auto_alpha(path, icon=True):
    logger.info("auto_alpha")
    DVR = 40
    img = Image.open(path).convert("RGB")
    if icon:
        SIZE = (img.width*400//max(img.size),
                img.height*400//max(img.size))
    else:
        SIZE = (img.width,img.height)

    img = img.resize(SIZE, Image.LANCZOS)

    gray = new_convert(img, "L")  # グレイスケール
    enhancer = ImageEnhance.Contrast(gray)
    gray = enhancer.enhance(2.0)

    gray.save("media/gray.png")
    img_mat = np.asarray(gray, dtype=np.uint8)
    gray2 = gray.filter(ImageFilter.MaxFilter(3))
    senga_inv = ImageChops.difference(gray, gray2)
    senga_inv = ImageOps.invert(senga_inv)
    enhancer = ImageEnhance.Contrast(senga_inv)
    senga_inv = enhancer.enhance(5.0)
    senga_inv.save("media/edge.png")
    edge = np.asarray(senga_inv)
    # 四隅から領域調査
    CS = set([0,255])
    for h, w in [(0, 0), (0, img.width//2), (0, img.width-1), (img.height//2, 0), (img.height//2, img.width-1), (img.height-1, 0), (img.height-1, img.width//2), (img.height-1, img.width-1)]:
        CS.add(img_mat[h, w])

    EDGE_VAL = 250
    max_mask = np.zeros((img_mat.shape), dtype=np.uint8)
    for c_min, c_max in [(max([0, i-DVR]), min([i+DVR, 255])) for i in CS]:
        mask = np.ones((img_mat.shape), dtype=np.uint8)
        for sh, sw in [(0, 0), (0, img.width//2), (0, img.width-1), (img.height//2, 0), (img.height//2, img.width-1), (img.height-1, 0), (img.height-1, img.width//2), (img.height-1, img.width-1)]:
            que = []
            if mask[sh, sw] == 1 and c_min <= img_mat[sh, sw] <= c_max:
                que.append((sh,sw))
            while len(que) > 0:
                h, w = que.pop(0)
                if mask[h, w] == 1:
                    if  edge[h, w] >= EDGE_VAL:
                        mask[h, w] = 255
                    else:
                        mask[h, w] = 0
                        continue
                else:
                    continue
                # 上
                if h - 1 >= 0:
                    que.append((h-1, w))
                # 下
                if h + 1 <= img.height - 1:
                    que.append((h+1, w))
                # 左
                if w - 1 >= 0:
                    que.append((h, w-1))
                # 右
                if w + 1 <= img.width - 1:
                    que.append((h, w+1))

        np.where(mask == 1, 0, mask)
        if np.sum(max_mask) < np.sum(mask):
            max_mask = mask

    # BB,GB対応
    
    if img.mode == "RGB":
        tmpmat = np.asarray(img)
        mask = np.zeros((img_mat.shape), dtype=np.uint8)
        for r,g,b in [(0,255,0), (0,0,255)]:
            for h in range(img.height):
                for w in range(img.width):
                    if r - DVR <= tmpmat[h, w][0] <= r + DVR and g - DVR <= tmpmat[h, w][1] <= g + DVR and b - DVR <= tmpmat[h, w][2] <= b + DVR:
                        mask[h, w] = 255

            if np.sum(max_mask) < np.sum(mask):
                max_mask = mask

    # 反転
    max_mask = 255 - max_mask
    max_mask = Image.fromarray(max_mask)
    max_mask = max_mask.filter(ImageFilter.MaxFilter(3))
    max_mask = max_mask.filter(ImageFilter.MinFilter(3))
    max_mask = max_mask.filter(ImageFilter.MaxFilter(3))
    max_mask = max_mask.filter(ImageFilter.GaussianBlur(2.0))
    max_mask.save("media/mask.png")
    img.putalpha(max_mask)
    retpath = path.split(".")[0] + "_putalpha.png"
    img.save(retpath)
    return retpath


#######################################################
# 線画化
def image_to_line(path): # img:RGBモード
    # 線画化
    img = Image.open(path)
    # gray = img.convert("L") #グレイスケール
    gray = new_convert(img, "L") #グレイスケール
    gray2 = gray.filter(ImageFilter.MaxFilter(5))
    senga_inv = ImageChops.difference(gray, gray2)
    senga_inv = ImageOps.invert(senga_inv)
    senga_inv.filter(ImageFilter.MedianFilter(5))
    save_path = "media/_templine.png"
    senga_inv.save(save_path)
    return save_path


def expand2square(pil_img, background_color):
    width, height = pil_img.size
    if width == height:
        return pil_img
    elif width > height:
        result = Image.new(pil_img.mode, (width, width), background_color)
        result.paste(pil_img, (0, (width - height) // 2))
        return result
    else:
        result = Image.new(pil_img.mode, (height, height), background_color)
        result.paste(pil_img, ((height - width) // 2, 0))
        return result


def image_resize(img, resize):
    # アスペクト比維持
    tmp = img.copy()
    # tmp.thumbnail(resize,Image.BICUBIC)
    if tmp.mode == 'L':
        tmp = expand2square(tmp,(255,))
    else:
        tmp = expand2square(tmp,(255,255,255))
    return tmp.resize(resize,Image.BICUBIC)


def crop_center(pil_img, crop_width, crop_height):
    img_width, img_height = pil_img.size
    return pil_img.crop(((img_width - crop_width) // 2,
                         (img_height - crop_height) // 2,
                         (img_width + crop_width) // 2,
                         (img_height + crop_height) // 2))


def new_convert(img, mode):
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
    elif img.mode == "LA":
        bg = Image.new("L", img.size, (255,))
        bg.paste(img, mask=img.split()[1])
    else:
        bg = img
    return bg.convert(mode)
