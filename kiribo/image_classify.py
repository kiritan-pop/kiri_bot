# Load and use the models
import numpy as np
from transformers import AutoImageProcessor
from optimum.onnxruntime import ORTModelForImageClassification
from PIL import Image
import unicodedata


ONNX_MODEL_PATH = "data/imgclsfy_r2/"
processor = AutoImageProcessor.from_pretrained(ONNX_MODEL_PATH)
onnx_model = ORTModelForImageClassification.from_pretrained(ONNX_MODEL_PATH)


def sigmoid(a):
    return 1 / (1 + np.exp(-a))


def predict(image, TH:float = 0.65):
    inputs = processor(images=image, return_tensors="np")
    outputs = onnx_model(**inputs)
    pred_labels = [unicodedata.normalize('NFC', onnx_model.config.id2label[idx]) for idx in list(np.argwhere(sigmoid(outputs.logits[0]) >= TH)[:,0])]
    return pred_labels


if __name__ == '__main__':
    image = Image.open("media/1a22cd5eb129a1b6.png").convert("RGB")
    print(predict(image))
