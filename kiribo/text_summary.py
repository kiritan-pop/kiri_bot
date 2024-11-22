from kiribo.openai_service import predict, is_alive


SYSTEM_PROMPT = """
入力された文章を要約してください。
（要約できない場合は、"要約なし"と回答してください）

出力フォーマット
```json
{
"summary_ja" : "要約した文章（日本語）"
}
```

出力例：要約なし
```json
{
"summary_ja" : "要約なし"
}
```

--
入力文章は以下です。

input:
"""

def get_summary(text: str):
    if is_alive():
      response = predict(SYSTEM_PROMPT, text)
      return response.get("summary_ja", text)
    else:
      return text
