from urllib.parse import urljoin
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


def predict(system_prompt, user_prompt, parameters=chatgpt_parameters):

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        completion = openai_client.chat.completions.create(
            messages=messages,
            **parameters
        )
        res_raw = completion.choices[0].message.content
        result = re.search(r"```json(?P<json_content>.+)```",
                            res_raw, flags=re.DOTALL)
        if result:
            res_raw = result.groupdict().get('json_content') or res_raw

        ret_dict = json.loads(res_raw)
        return ret_dict

    except Exception as e:
        logger.error(str(e))
        return dict()        
