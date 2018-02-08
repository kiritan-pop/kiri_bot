from keras.preprocessing.image import ImageDataGenerator, load_img, img_to_array, array_to_img
from keras.applications.vgg16 import VGG16
from keras.models import Sequential,Model,load_model
from keras.layers import Input, Dense, Dropout, Activation, Flatten
from keras.optimizers import SGD
from keras.utils.np_utils import to_categorical
from keras.callbacks import TensorBoard, LambdaCallback
from keras.utils.training_utils import multi_gpu_model
import multiprocessing
import os,glob,sys,json
import numpy as np
from PIL import Image

import tensorflow as tf
from keras.backend import tensorflow_backend
config = tf.ConfigProto(gpu_options=tf.GPUOptions(allow_growth=True))
session = tf.Session(config=config)
tensorflow_backend.set_session(session)

# 同時実行プロセス数
process_count = multiprocessing.cpu_count()

STANDARD_SIZE = (299, 299)
#STANDARD_SIZE = (224, 224)
batch_size = 64
epochs = 10
path_list = []
image_list = []
label_list = []
img_dir = 'images/'
test_dir = 'test_images/'

# モデルを読み込む
model = load_model('../db/tako3.h5')
#model.summary()

start_idx = 0
if len(sys.argv) == 2 :
    if sys.argv[1].isdigit():
        start_idx = int(sys.argv[1])

train_datagen = ImageDataGenerator(
                rescale=1./255,
                rotation_range=45, # 90°まで回転
                width_shift_range=0.1, # 水平方向にランダムでシフト
                height_shift_range=0.1, # 垂直方向にランダムでシフト
                channel_shift_range=50.0, # 色調をランダム変更
                shear_range=0.39, # 斜め方向(pi/8まで)に引っ張る
                horizontal_flip=True, # 垂直方向にランダムで反転
                vertical_flip=True, # 水平方向にランダムで反転
                zoom_range=0.5,
                )

#test_datagen = ImageDataGenerator(rescale=1./255)

# 画像の拡張
train_generator = train_datagen.flow_from_directory(
    img_dir,
    #save_to_dir='gen_images',
    batch_size=batch_size,
    target_size=STANDARD_SIZE)
validation_generator = train_datagen.flow_from_directory(
    img_dir,
    batch_size=batch_size,
    target_size=STANDARD_SIZE)

print(type(train_generator.class_indices))
print(train_generator.class_indices)
with open('../.cnn_labels','w') as fw:
    json.dump(train_generator.class_indices,fw,indent=4)

def on_epoch_end(epoch, logs):
    model.save('../db/tako3.h5')

print_callback = LambdaCallback(on_epoch_end=on_epoch_end)
multi_model = multi_gpu_model(model, gpus=2)
multi_model.compile(loss='categorical_crossentropy',
              optimizer=SGD(lr=1e-3, decay=1e-6, momentum=0.9, nesterov=True),
              metrics=['accuracy'])

#model.fit_generator(
multi_model.fit_generator(
        train_generator,
        callbacks=[print_callback],
        steps_per_epoch=2000,
        epochs=epochs,
        validation_data=validation_generator,
        validation_steps=100,
        initial_epoch=start_idx,
        max_queue_size=process_count * 10,
        workers=process_count,
        use_multiprocessing=True)
