class KiriConfig:

    MODEL_NAME = "sonoisa/t5-base-japanese-v1.1"
    SAVE_PATH = "data/t5_model/model.onnx"
    QUANTIZED_MODEL_PATH = "data/t5_model/model.onnx.quant"

    MAX_LENGTH = 192
    MAX_INPUT_LENGTH = MAX_LENGTH
    SEP = "|"
    ENCODER_OUTPUT_DIM = 384  # 768 # 384
    MAX_CHAR_LEN = 64
    MAX_OUTPUT_LENGTH = MAX_CHAR_LEN
