# -*- coding: utf-8 -*-

import os

MU = "🧪"       # 無 padding
UNK = "🎴"      # アンノーン
STR = "🦷"      # 始まりマーク
CTOKENS = [MU, UNK, STR]


class KiriDataLoader:
    def __init__(self, tokenizer, config) -> None:
        self.tokenizer = tokenizer
        self.config = config

        # 使用する文字種
        assert  os.path.exists(self.config.WL_PATH)

        wl_chars = list(open(self.config.WL_PATH).read())
        wl_chars = CTOKENS + wl_chars
        self.char_size = len(wl_chars)
        self.char_idx = {c: i for i, c in enumerate(wl_chars)}
        self.idx_char = {i: c for i, c in enumerate(wl_chars)}

        assert self.char_size == config.VOCAB_SIZE
        assert len(self.char_idx) == config.VOCAB_SIZE
        assert len(self.idx_char) == config.VOCAB_SIZE
