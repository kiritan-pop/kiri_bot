import re
import json
import wikipedia
from kiribo.openai_service import predict, is_alive


wikipedia.set_lang("ja")
wikipedia.set_user_agent("kiri_bot (https://github.com/kiritan-pop/kiri_bot/)")


SYSTEM_PROMPT = """与えられた単語について、wikipediaの要約を取得しました。
wikipediaの情報を参考にして、意味と内容の解説をしてください。
- wikipediaの情報がない場合、もしくは明らかに間違っている場合は、あなたの知識を使って解説してください

出力フォーマット
```json
{
    "answer": "回答内容（通常版ですます口調）" or null
}
```

input:
"""

# - お嬢様口調バージョンの回答も作成してください。
# "noble_answer": "回答内容（お嬢様口調）" or null
# **注意事項**
# 「お嬢様口調」とは、主に裕福で品のある家庭の令嬢（お嬢様）が使いそうな、上品で丁寧な言葉遣いや話し方のことを指します。
# フィクション作品やキャラクター表現の一環としてよく見られる言葉遣いです。

# 特徴としては以下のようなものがあります：
# - 丁寧な言葉遣い: 「ですわ」「でしてよ」「ございます」など、より丁寧な語尾や表現が多用される。
# - 上品な語彙の選択: 日常的な言葉でも、上品で古風な表現を用いることがある。



def llm_predict(word: str, wikipedia_summary: str):
    if is_alive():
        prompt = dict(
            word=word,
            wikipedia_summary=wikipedia_summary if wikipedia_summary else "（wikipediaから情報取得できませんでした）",
        )
        response = predict(SYSTEM_PROMPT, json.dumps(prompt, ensure_ascii=False, indent=2))
        return response.get("answer")
    else:
        return None


def sensesearch(word: str):
    if len(word) == 0:
        return ""
    
    try:
        summary = wikipedia.summary(word, auto_suggest=False)
    except Exception:
        summary = ""

    result = llm_predict(word, summary)
    if result:
        return result
    else:
        return summary


if __name__ == '__main__':
    # text = llm_predict("潮騒", "")
    # print(text)
    print(is_alive())
