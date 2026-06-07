import re
import json
import wikipedia
from kiribo.openai_service import predict, is_alive


wikipedia.set_lang("ja")
wikipedia.set_user_agent("kiri_bot (https://github.com/kiritan-pop/kiri_bot/)")


SYSTEM_PROMPT = """
# instruction
与えられた単語・文章について、wikipediaの要約を取得しました。
wikipediaの情報を参考にして、意味と内容の解説をしてください。
- 文体："敬体"ではなく"常体"で回答してください。
- 以下のような場合は、文脈や語感から想像して、それっぽい解説を作成してください。
  - wikipediaから情報が取得できなかった場合
  - wikipediaの要約が明らかに間違っている場合
  - 全く無意味な単語の場合

# 入力フォーマット(JSON)
```json
{
    "word": "単語・文章",
    "wikipedia_summary": "wikipediaの要約"
}
```

# 出力フォーマット(JSONコードブロックのみ出力してください)
```json
{
    "answer": "回答内容"
}
```

# 出力例1
input:
```json
{
    "word": "富士山",
    "wikipedia_summary": 富士山は、日本の活火山である。標高は3775.56 m、山体の最高地点は3776.12 mで、日本最高峰の独立峰で、その優美な風貌は日本国外でも日本の象徴として広く知られている。山梨県と静岡県に跨る。 数多くの芸術作品の題材とされ芸術面のみならず、気候や地層など地質学的にも社会に大きな影響を与えている。"
}
```

output:
```json
{
    "answer": "富士山は、日本の活火山である。標高は3775.56 m、山体の最高地点は3776.12 mで、日本最高峰の独立峰で、その優美な風貌は日本国外でも日本の象徴として広く知られている。山梨県と静岡県に跨る。 数多くの芸術作品の題材とされ芸術面のみならず、気候や地層など地質学的にも社会に大きな影響を与えている。"
}
```

# 出力例2
input:
```json
{
    "word": "クメ菜",
    "wikipedia_summary": "（wikipediaから情報取得できませんでした）"
}
```
output:
```json
{
    "answer": "美味しくなく、栄養価も低い野菜である。"
}
`

# 実際のデータは以下の通り
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
        response = predict(SYSTEM_PROMPT, json.dumps(prompt, ensure_ascii=False, indent=2) + "\noutput:\n")
        return response.get("answer")
    else:
        return None


def sensesearch(word: str):
    word = word.strip()
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
