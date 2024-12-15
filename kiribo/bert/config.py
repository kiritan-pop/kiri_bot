# -*- coding: utf-8 -*-
# config
class KiriConfig:
    MODEL_NAME = 'intfloat/multilingual-e5-small'
    # MODEL_NAME = 'intfloat/multilingual-e5-base'
    # MODEL_NAME = "studio-ousia/luke-japanese-base-lite"
    # MODEL_NAME = 'ku-nlp/deberta-v2-base-japanese'
    SAVE_PATH = "data/bert/model_quant.onnx"
    SPM_MODEL = "data/bert/spm_model.model"

    MAX_LENGTH = 256
    MAX_CHAR_LEN = 128
    VOCAB_SIZE = 8000
