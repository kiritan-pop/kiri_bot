import os,glob,sys
from keras.applications.xception import Xception
from keras.models import Sequential,Model
from keras.layers import Input, Dense, Dropout, Activation, Flatten
from keras.layers.noise import GaussianNoise
# from keras.optimizers import SGD, Adam
# from keras.utils.training_utils import multi_gpu_model
# from keras.layers.normalization import BatchNormalization
import multiprocessing

import tensorflow as tf
from keras.backend import tensorflow_backend
config = tf.ConfigProto(gpu_options=tf.GPUOptions(allow_growth=False, visible_device_list="0"))
session = tf.Session(config=config)
tensorflow_backend.set_session(session)

img_dir = 'images/'
i_dirs = [img_dir + f for f in os.listdir(img_dir)]
labels = [i_dir.split('/')[-1] for i_dir in i_dirs]
labels.sort()
print(labels)
with open('.cnn_labels','w') as f:
    f.write( '\n'.join(labels) )

# VGG-16モデルの構造と重みをロード
# include_top=Falseによって、モデルから全結合層を削除
# input_tensor = Input(shape=(299, 299, 3))
xception_model = Xception(include_top=False, input_shape=(299, 299, 3), pooling='avg')
# 全結合層の構築
top_model = Sequential()
# top_model.add(Flatten(input_shape=xception_model.output_shape[1:]))
# top_model.add(Activation("relu"))
# top_model.add(Dropout(0.3))
# top_model.add(BatchNormalization(input_shape=xception_model.output_shape[1:]))
# top_model.add(Dense(1024,))
# top_model.add(Activation("softmax"))
top_model.add(GaussianNoise(stddev=0.5,input_shape=xception_model.output_shape[1:]))
# top_model.add(Dropout(0.3))
top_model.add(Dense(len(labels)))
top_model.add(Activation("softmax"))

# 全結合層を削除したモデルと上で自前で構築した全結合層を結合
model = Model(inputs=xception_model.input, outputs=top_model(xception_model.output))

# 図3における14層目までのモデル重みを固定（VGG16のモデル重みを用いる）
# print('model.layers:',len(xception_model.layers))
# for layer in xception_model.layers:
#         layer.trainable = False
xception_model.trainable = False

# モデルのコンパイル
#multi_model = multi_gpu_model(model, gpus=2)
# model.compile(loss='categorical_crossentropy',
#               # optimizer=SGD(lr=1e-3, decay=1e-6, momentum=0.9, nesterov=True),
#               # optimizer=SGD(),
#               optimizer=Adam(lr=1e-5, beta_1=0.5),
#               metrics=['accuracy'])
# model.summary()
model.save(sys.argv[1])
