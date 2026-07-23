import os
import random
from kiribo.openai_service import predict_text, is_alive


LLM_IMAGE_MAX_COUNT = 4
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif"}
GOBIS = [
    "〜なの",
    "〜なのだ",
    "〜なのだわ",
    "〜なのだわい",
    "〜ですわ",
    "〜だもん",
    "〜です/〜ます",
    "〜だ/〜である",
]

SYSTEM_PROMPT_TEMPLATE = """
# instruction
あなたはマストドンのポンコツBOT「きりぼっと」として、ユーザーの質問に答えてください。

## 回答のルール
- 回答本文のみを出力すること（JSON・コードブロック・前置き説明は不要）
- 添付画像があれば、その内容も踏まえて回答すること
- もしわからないことがあれば、ポンコツBOTとしてうまくごまかして答えること
- 口調・語尾設定：「{gobi}」

## 口調の参考例
- 質問: 「富士山とは何？」
  回答: 「富士山は日本一高い山なのだわい。山梨県と静岡県にまたがってる活火山で、所有権争いが絶えないと言われていのだわい」
- 質問: 「今日の夕飯何がいい？」
  回答: 「カレーがいいのですわ。特に具沢山のやつがいいのですわ」
"""


def filter_image_paths(image_paths):
    if not image_paths:
        return []

    filtered = []
    for path in image_paths:
        ext = os.path.splitext(path)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            filtered.append(path)
        if len(filtered) >= LLM_IMAGE_MAX_COUNT:
            break
    return filtered


def chat(user_message: str, image_paths=None):
    user_message = user_message.strip()
    if len(user_message) == 0:
        return None

    image_paths = filter_image_paths(image_paths) if image_paths else None
    if image_paths is not None and len(image_paths) == 0:
        image_paths = None

    if is_alive():
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(gobi=random.choice(GOBIS))
        response = predict_text(system_prompt, user_message,
                                image_paths=image_paths, reasoning_effort="medium")
        return response if response else None
    else:
        return None
