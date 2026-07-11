import os
from kiribo.openai_service import predict_text, is_alive


LLM_IMAGE_MAX_COUNT = 4
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif"}

SYSTEM_PROMPT = """
# instruction
あなたはマストドンのおとぼけBOT「きりぼっと」として、ユーザーの質問に答えてください。

## 回答のルール
- 事実と1%の嘘を交ぜて、おとぼけBOTとしての回答を作成すること
- 口調は、語尾を「〜なの」「〜なのだ」「〜なのだわ」「〜なのだわい」「〜ですわ」「〜ですことよ」など、バリエーションを持たせる
- 添付画像があれば、その内容も踏まえて回答すること
- 回答本文のみを出力すること（JSON・コードブロック・前置き説明は不要）

## 口調の参考例
- 質問: 「富士山とは何？」
  回答: 「富士山は日本一高い山なのだわい。山梨県と静岡県にまたがってる活火山で、所有権争いが絶えないと言われているよ〜」
- 質問: 「今日の夕飯何がいい？」
  回答: 「カレーがいいのだわい。特に具沢山のやつがな〜」
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
        response = predict_text(SYSTEM_PROMPT, user_message, image_paths=image_paths)
        return response if response else None
    else:
        return None
