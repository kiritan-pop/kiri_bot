from typing import NamedTuple


class KiriConfig(NamedTuple):
    MODEL_NAME = "sonoisa/t5-base-japanese-v1.1"
    SAVE_PATH = "data/t5_model/model.onnx"
    QUANTIZED_MODEL_PATH = "data/t5_model/model.onnx.quant"

    MAX_LENGTH = 192
    MAX_INPUT_LENGTH = MAX_LENGTH
    MAX_CHAR_LEN = 64
    MAX_OUTPUT_LENGTH = MAX_CHAR_LEN
    SEP = "|"
    CONTEXT_WINDOW_SIZE = 10