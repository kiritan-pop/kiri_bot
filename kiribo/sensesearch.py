import re
import wikipedia
from kiribo.openai_service import predict, is_alive


wikipedia.set_lang("ja")
wikipedia.set_user_agent("kiri_bot (https://github.com/kiritan-pop/kiri_bot/)")


SYSTEM_PROMPT = """与えられた言葉の意味と解説をしてください。
わからない場合は null を回答すること。

出力フォーマット
```json
{
    "answer": "回答内容" or null
}
```

input:
"""

# また、お嬢様口調バージョンの回答も作成してください。

# **注意事項**
# 「お嬢様口調」とは、主に裕福で品のある家庭の令嬢（お嬢様）が使いそうな、上品で丁寧な言葉遣いや話し方のことを指します。
# フィクション作品やキャラクター表現の一環としてよく見られる言葉遣いです。

# 特徴としては以下のようなものがあります：
# - 丁寧な言葉遣い: 「ですわ」「でしてよ」「ございます」など、より丁寧な語尾や表現が多用される。
# - 上品な語彙の選択: 日常的な言葉でも、上品で古風な表現を用いることがある。


def llm_predict(word: str):
    if is_alive():
      response = predict(SYSTEM_PROMPT, word)
      return response.get("answer")
    else:
      return None


def sensesearch(word: str):
    word = re.sub(
        r".*(へい)?きりぼ(っと)?(くん|君|さん|様|さま|ちゃん)?[!,.]?", "", word).strip()
    if len(word) == 0:
        return ""
    
    result = llm_predict(word)
    if result:
        return result

    try:
        page = wikipedia.page(word)
    except wikipedia.exceptions.DisambiguationError as e:
        nl = "\n"
        return f'「{word}」にはいくつか意味があるみたいだよ〜{nl}次のいずれかのキーワードでもう一度調べてね〜{nl}{",".join(e.options)}'
    except Exception as e:
        return f'え？「{word}」しらなーい！'
    else:
        return page.summary



