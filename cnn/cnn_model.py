import os,glob,sys
from tensorflow.python.keras.applications.xception import Xception
from tensorflow.python.keras.models import Sequential,Model
from tensorflow.python.keras.layers import Input, Dense, Dropout, Activation, Flatten
from tensorflow.python.keras.layers import GaussianNoise
from tensorflow.python.keras import backend as tensorflow_backend
from tensorflow.python.keras.layers import BatchNormalization

# import tensorflow as tf
# config = tf.ConfigProto(gpu_options=tf.GPUOptions(allow_growth=False, visible_device_list="2"))
# session = tf.Session(config=config)
# tensorflow_backend.set_session(session)

def cnn_model(labels):
    # include_top=Falseによって、モデルから全結合層を削除
    input_tensor = Input(shape=(299, 299, 3))
    # input_tensor = GaussianNoise(stddev=0.1)(input_tensor)
    # xception_model = Xception(include_top=False, input_shape=(299, 299, 3), pooling='avg')
    xception_model = Xception(include_top=False, pooling='avg', input_tensor=input_tensor)
    # 全結合層の構築
    top_model = Sequential()
    # top_model.add(Flatten(input_shape=xception_model.output_shape[1:]))
    # top_model.add(Activation("relu"))
    # top_model.add(Dropout(0.3))
    # top_model.add(Dense(1024,))
    # top_model.add(Activation("softmax"))
    # top_model.add(BatchNormalization(input_shape=xception_model.output_shape[1:]))
    top_model.add(GaussianNoise(stddev=0.3,input_shape=xception_model.output_shape[1:]))
    # top_model.add(Dropout(0.3))
    top_model.add(Dense(len(labels)))
    top_model.add(Activation("softmax"))

    # 全結合層を削除したモデルと上で自前で構築した全結合層を結合
    model = Model(inputs=xception_model.input, outputs=top_model(xception_model.output))

    # 図3における14層目までのモデル重みを固定（VGG16のモデル重みを用いる）
    # print('model.layers:',len(xception_model.layers))
    # xception_model.trainable = False
    for layer in xception_model.layers[:-5]:
        layer.trainable = False
    return model
