# -*- coding: utf-8 -*-

from .predict_t5 import gen_text
from .config import KiriConfig as T5Config

if __name__ == '__main__':
    # テスト用
    print(gen_text(["こんにちは"]))
