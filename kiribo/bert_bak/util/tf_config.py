# -*- coding: utf-8 -*-
import os
import tensorflow as tf

def tf_config(gpu_id = 0):
    print(f"{tf.__version__}")
    # try:
    if tf.__version__ >= "2.1.0":
        if 'COLAB_TPU_ADDR' in os.environ:
            resolver = tf.distribute.cluster_resolver.TPUClusterResolver(tpu='grpc://' + os.environ['COLAB_TPU_ADDR'])
            tf.config.experimental_connect_to_cluster(resolver)
            # This is the TPU initialization code that has to be at the beginning.
            tf.tpu.experimental.initialize_tpu_system(resolver)
            tf.distribute.experimental.TPUStrategy(resolver)
        else:
            physical_devices = tf.config.list_physical_devices('GPU')
            tf.config.list_physical_devices('GPU')
            tf.config.set_visible_devices(physical_devices[gpu_id], 'GPU')
            # docker上だと以下は設定できなさそう
            # tf.config.experimental.set_memory_growth(
            #     physical_devices[gpu_id], True)
    elif tf.__version__ >= "2.0.0":
        #TF2.0
        physical_devices = tf.config.experimental.list_physical_devices('GPU')
        tf.config.experimental.set_visible_devices(
            physical_devices[gpu_id], 'GPU')
        tf.config.experimental.set_memory_growth(
            physical_devices[gpu_id], True)
    else:
        raise Exception(f"tensorflowのバージョンが古いです。{tf.__version__} < 2.0.0 ")
    # except Exception as e:
    #     print(e)