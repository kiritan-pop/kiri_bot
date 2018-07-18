from tensorflow.python.keras.preprocessing.image import ImageDataGenerator
# from keras.applications.vgg16 import VGG16
# from keras.models import Sequential,Model,load_model
# from keras.layers import Input, Dense, Dropout, Activation, Flatten
from tensorflow.python.keras.optimizers import Adam
# from tensorflow.python.keras.utils.np_utils import to_categorical
from tensorflow.python.keras.callbacks import LambdaCallback,EarlyStopping
# from tensorflow.python.keras.utils.training_utils import multi_gpu_model
import multiprocessing
import os,glob,sys,json
from cnn_model import cnn_model
import numpy as np
from PIL import Image

import tensorflow as tf
from tensorflow.python.keras import backend as tensorflow_backend
config = tf.ConfigProto(gpu_options=tf.GPUOptions(allow_growth=False,
                                                  visible_device_list='2'
                                                  ))
session = tf.Session(config=config)
tensorflow_backend.set_session(session)

# 同時実行プロセス数
process_count = multiprocessing.cpu_count()

GPUs = 1
STANDARD_SIZE = (299, 299)
#STANDARD_SIZE = (224, 224)
batch_size = (96)*GPUs
epochs = 100000
path_list = []
image_list = []
label_list = []
img_dir = 'images/'
test_dir = 'test_images/'
model_path = sys.argv[1]

start_idx = 0
if len(sys.argv) == 3 :
    if sys.argv[2].isdigit():
        start_idx = int(sys.argv[2])

train_datagen = ImageDataGenerator(
                rescale=1./255,
                rotation_range=90, # 90°まで回転
                width_shift_range=0.2, # 水平方向にランダムでシフト
                height_shift_range=0.2, # 垂直方向にランダムでシフト
                #channel_shift_range=50.0, # 色調をランダム変更
                shear_range=0.2, # 斜め方向(pi/8まで)に引っ張る
                horizontal_flip=True, # 垂直方向にランダムで反転
                vertical_flip=True, # 水平方向にランダムで反転
                zoom_range=0.2,
                fill_mode='wrap'
                )

#test_datagen = ImageDataGenerator(rescale=1./255)

# 画像の拡張
train_generator = train_datagen.flow_from_directory(
    img_dir,
    batch_size=batch_size,
    target_size=STANDARD_SIZE)
validation_generator = train_datagen.flow_from_directory(
    img_dir,
    batch_size=batch_size,
    target_size=STANDARD_SIZE)

print(train_generator.class_indices)
with open('.cnn_labels','w') as fw:
    json.dump(train_generator.class_indices,fw,indent=4)

# モデルを読み込む
model = cnn_model(train_generator.class_indices)
model.summary()
if os.path.exists(model_path):
    model.load_weights(model_path + 'w', by_name=False)

def on_epoch_end(epoch, logs):
    model.save_weights(model_path + 'w')
    model.save(model_path)


print_callback = LambdaCallback(on_epoch_end=on_epoch_end)
ES = EarlyStopping(monitor='loss', min_delta=0.001, patience=10, verbose=0, mode='auto')

# if GPUs > 1:
#     t_model = multi_gpu_model(model, gpus=GPUs)
# else:
#     t_model = model
model.compile(loss='categorical_crossentropy',
              # optimizer=SGD(lr=1e-3, decay=1e-6, momentum=0.9, nesterov=True),
              # optimizer=SGD(),
              optimizer=Adam(),
              # optimizer=Adam(lr=1e-5, beta_1=0.5),
              metrics=['accuracy'])
model.summary()
model.fit_generator(
        train_generator,
        callbacks=[print_callback,ES],
        # steps_per_epoch=512,
        epochs=epochs,
        validation_data=validation_generator,
        validation_steps=15,
        initial_epoch=start_idx,
        max_queue_size=process_count,
        workers=3,
        use_multiprocessing=True)
