from urllib.parse import urljoin
import base64
import mimetypes
import requests
import re
import json
import openai
from kiribo.config import settings

import logging
logger = logging.getLogger(__name__)


openai_client = openai.OpenAI(
    base_url=settings.openai_api_base,
    api_key=settings.openai_api_key)


chatgpt_parameters = dict(
    model=settings.openai_model,
    temperature=settings.openai_temperature,
)


def is_alive():
    url = urljoin(settings.openai_api_base, "models/")

    """HTTPサーバーが生きているか確認"""
    try:
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            return True
        else:
            return False
    except requests.RequestException:
        return False


def encode_image(image_path: str):
    with open(image_path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode('utf-8')
    mime_type, _ = mimetypes.guess_type(image_path)
    if mime_type is None:
        mime_type = "application/octet-stream"
    return encoded, mime_type


def _build_user_content(user_prompt: str, image_paths=None):
    if not image_paths:
        return user_prompt

    content = [{"type": "text", "text": user_prompt}]
    for image_path in image_paths:
        try:
            base64_image, mime_type = encode_image(image_path)
        except Exception as e:
            logger.error(f"encode_image failed: {image_path}: {e}")
            continue
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{base64_image}"},
        })

    if len(content) == 1:
        return user_prompt
    return content


def _chat_completion(system_prompt, user_prompt, parameters=chatgpt_parameters, image_paths=None):
    user_content = _build_user_content(user_prompt, image_paths)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    completion = openai_client.chat.completions.create(
        messages=messages,
        reasoning_effort="none",
        **parameters
    )
    return completion.choices[0].message.content or ""


def predict(system_prompt, user_prompt, parameters=chatgpt_parameters):
    try:
        res_raw = _chat_completion(system_prompt, user_prompt, parameters)
        result = re.search(r"```json(?P<json_content>.+)```",
                            res_raw, flags=re.DOTALL)
        if result:
            res_raw = result.groupdict().get('json_content') or res_raw

        ret_dict = json.loads(res_raw)
        return ret_dict

    except Exception as e:
        logger.error(str(e))
        return dict()


def predict_text(system_prompt, user_prompt, parameters=chatgpt_parameters, image_paths=None):
    """プレーンテキスト応答を返す（JSONパースなし）"""
    try:
        return _chat_completion(
            system_prompt, user_prompt, parameters, image_paths=image_paths
        ).strip()
    except Exception as e:
        logger.error(str(e))
        return ""


if __name__ == '__main__':
    print(f"{is_alive()=}")
