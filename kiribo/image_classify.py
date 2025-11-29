# kiribo/image_classify.py (修正版)
import os
import numpy as np
from transformers import AutoImageProcessor
import onnxruntime as ort  # optimum ではなく onnxruntime を直接使用
from PIL import Image
import unicodedata
import json

# モデルディレクトリへのパス
MODEL_DIR = "data/imgclsfy_r2/"
# ONNXファイルのパス (Optimumでexportした場合、通常 model.onnx という名前です)
ONNX_MODEL_PATH = os.path.join(MODEL_DIR, "model.onnx")

# プロセッサは transformers のままでOK (Torch不要で動きます)
processor = AutoImageProcessor.from_pretrained(MODEL_DIR)

# ONNX Runtime セッションの作成
session = ort.InferenceSession(ONNX_MODEL_PATH, providers=['CPUExecutionProvider'])

# ラベル情報の読み込み (config.json から取得)
# Optimumを使わない場合、ラベルIDのマップを手動でロードする必要があります
try:
    with open(os.path.join(MODEL_DIR, "config.json"), "r") as f:
        config = json.load(f)
        # id2label はキーが文字列で保存されていることが多いので int に変換
        id2label = {int(k): v for k, v in config.get("id2label", {}).items()}
except Exception as e:
    print(f"Warning: config.json logic failed: {e}")
    id2label = {}

def sigmoid(a):
    return 1 / (1 + np.exp(-a))

def predict(image, TH: float = 0.65):
    # 前処理 (return_tensors="np" で NumPy 配列として受け取るのが重要)
    inputs = processor(images=image, return_tensors="np")
    
    # ONNX Runtime への入力準備
    # モデルの入力名を取得 (通常は 'pixel_values')
    input_name = session.get_inputs()[0].name
    
    # 推論実行
    # outputs はリスト形式で返ります [logits, ...]
    ort_inputs = {input_name: inputs['pixel_values']}
    outputs = session.run(None, ort_inputs)
    
    # ロジットの取得 (最初の要素がlogits)
    logits = outputs[0]

    # 判定ロジック (元のコードを維持)
    # np.argwhere の結果を使って id2label からラベル名を引く
    pred_labels = [
        unicodedata.normalize('NFC', id2label[idx]) 
        for idx in list(np.argwhere(sigmoid(logits[0]) >= TH)[:, 0])
    ]
    return pred_labels

if __name__ == '__main__':
    # テスト用
    try:
        image = Image.open("media/0ced59569082acea.jpg").convert("RGB")
        print(predict(image))
    except FileNotFoundError:
        print("Test image not found.")