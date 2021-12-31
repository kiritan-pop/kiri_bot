# -*- coding: utf-8 -*-

import os
import json
import re
from more_itertools import repeatfunc
import random
import logging
import tensorflow as tf
import numpy as np

logging.basicConfig(level=logging.INFO)

class KiriDataset:
    MU = "🧪"       # 無 padding
    UNK = "🎴"      # アンノーン
    STR = "🦷"      # 始まりマーク
    CTOKENS = [MU, UNK, STR]
    def __init__(self, tokenizer, config, encoder_model=None) -> None:
        logging.info('*** data initializing***')
        self.tokenizer = tokenizer
        self.config = config
        self.encoder_model = encoder_model
        # 使用する文字種
        # todo:推論時 wl.txtがあればtoot.txtがなくてもいい
        if not os.path.exists(self.config.WL_PATH):
            self.make_char_whitelist()

        wl_chars = list(open(self.config.WL_PATH).read())
        wl_chars = KiriDataset.CTOKENS + wl_chars
        self.char_size = len(wl_chars)
        self.idx_char = {i:c for i,c in enumerate(wl_chars)}
        self.char_idx = {c:i for i,c in enumerate(wl_chars)}

        self.lines_q = []
        self.lines_a = []
        self.val_q = []
        self.val_a = []
        self.tf_ds = None
        self.tf_ds_val = None


    def make_char_whitelist(self):
        cnt_dict = {}
        with open(self.config.DATA_FILE_PATH) as f:
            lines = json.load(f)
        for toot in lines:
            for c in toot:
                if c in cnt_dict:
                    cnt_dict[c] += 1
                else:
                    cnt_dict[c] = 1

        # # ツイッターデータ
        with open(self.config.DATA_FILE2_PATH) as f:
            list_data = json.load(f)
        for q, a in list_data:
            for c in q.strip():
                if c in cnt_dict:
                    cnt_dict[c] += 1
                else:
                    cnt_dict[c] = 1
            for sen in a:
                for c in sen.strip():
                    if c in cnt_dict:
                        cnt_dict[c] += 1
                    else:
                        cnt_dict[c] = 1

        # 使う文字を頻度順にソート、選択
        sorted_dict = {}
        for k, v in sorted(cnt_dict.items(), key=lambda x: -x[1]):
            sorted_dict[k] = v

        with open("data/cnt_char.json", "w") as f:
            json.dump(sorted_dict, f, ensure_ascii=False, indent=2)
        wl_chars = list(sorted_dict.keys())
        wl_chars = wl_chars[:self.config.VOCAB_SIZE]
        wl_chars = [c for c in wl_chars if c not in KiriDataset.CTOKENS]
        print(f"wl_chars:{len(wl_chars)}")

        with open(self.config.WL_PATH, "w") as f:
            f.writelines(wl_chars)


    def read_input_data(self):
        logging.info('*** reading data ***')
        with open(self.config.DATA_FILE_PATH) as f:
            lines = json.load(f)

        lines = [l.strip() for l in lines]
        valnum = self.config.BATCH_SIZE * 10
        for size in range(2, self.config.SUM_LINES_SIZE + 1):
            tmp_q = []
            tmp_a = []
            for i in range(len(lines) - size):
                tmp_q.append(
                    self.config.SEP.join(lines[i:i + size]))
                tmp_a.append(
                    lines[i + size])

            # バリデーションデータ分割
            self.val_q.extend(tmp_q[:valnum])
            self.val_a.extend(tmp_a[:valnum])
            self.lines_q.extend(tmp_q[valnum:])
            self.lines_a.extend(tmp_a[valnum:])


        # ツイッターデータ
        with open(self.config.DATA_FILE2_PATH) as f:
            list_data = json.load(f)

        list_data = [(q.strip(), [a.strip() for a in al]) for q, al in list_data]
        tmp_q = []
        tmp_a = []
        for qes, ans_list in list_data:
            if len(qes) <= 5:
                continue
            if re.search(r"[あ-んア-ン]", qes) is None:
                continue
            for ans in ans_list:
                if len(ans) <= 5:
                    continue
                if re.search(r"[あ-んア-ン]", ans) is None:
                    continue
                tmp_q.append(qes)
                tmp_a.append(ans)

        # バリデーションデータ分割
        self.val_q.extend(tmp_q[-valnum:])
        self.val_a.extend(tmp_a[-valnum:])
        self.lines_q.extend(tmp_q[:-valnum])
        self.lines_a.extend(tmp_a[:-valnum])


        logging.info(f'*** data len = {len(self.lines_a)}***')
        logging.info(f'*** val len = {len(self.val_a)}***')
        with open("data/tmp_train.json", 'w') as f:
            json.dump([[q, a] for q, a in zip(self.lines_q[:1000] + self.lines_q[-1000:], self.lines_a[:1000] + self.lines_a[-1000:])],
                      f, ensure_ascii=False, indent=2)
        with open("data/tmp_val.json", 'w') as f:
            json.dump([[q, a] for q, a in zip(self.val_q, self.val_a)],
                      f, ensure_ascii=False, indent=2)

    def build_tf_ds(self):
        logging.info('*** building tf.dataset ***')

        def gen():
            nums = list(range(len(self.lines_a)))
            # 無限ジェネレーター
            iter = repeatfunc(random.sample, None, nums, len(nums))
            for num_list in iter:
                for i1 in num_list:
                    # input テキストのトークナイズ
                    input_text = self.lines_q[i1]
                    input_token_dic = self.tokenizer(input_text,
                                                    truncation=True, max_length=512, return_tensors="tf")

                    if len(input_token_dic['input_ids']) > self.config.MAX_LENGTH:
                        input_token_dic['input_ids'] = input_token_dic['input_ids'][:, -self.config.MAX_LENGTH:]
                        input_token_dic['attention_mask'] = input_token_dic['attention_mask'][:, -self.config.MAX_LENGTH:]
                        input_token_dic['token_type_ids'] = input_token_dic['token_type_ids'][:, -self.config.MAX_LENGTH:]
                    else:
                        input_token_dic = self.tokenizer(input_text, padding='max_length',
                                                        truncation=True, max_length=self.config.MAX_LENGTH, return_tensors="tf")

                    toot = KiriDataset.STR + self.lines_a[i1]
                    idxs = np.zeros((self.config.MAX_CHAR_LEN + 1,), dtype=int)
                    for i2 in range(min([self.config.MAX_CHAR_LEN + 1, len(toot)])):
                        if toot[i2] in self.char_idx:
                            idxs[i2] = self.char_idx[toot[i2]]
                        else:
                            idxs[i2] = self.char_idx[KiriDataset.UNK]

                    yield ((input_token_dic['input_ids'][0], input_token_dic['attention_mask'][0], idxs[:-1]), idxs[1:])

        if len(self.lines_a) == 0:
            self.read_input_data()
        tf_ds = tf.data.Dataset.from_generator(
            gen,
            output_signature=(
                (
                    tf.TensorSpec(
                        shape=(self.config.MAX_LENGTH,), dtype=tf.int16),
                    tf.TensorSpec(
                        shape=(self.config.MAX_LENGTH,), dtype=tf.int16),
                    tf.TensorSpec(
                        shape=(self.config.MAX_CHAR_LEN,), dtype=tf.int16),
                ),
                tf.TensorSpec(
                    shape=(self.config.MAX_CHAR_LEN,), dtype=tf.int16),
            )
        )
        tf_ds = tf_ds.batch(self.config.BATCH_SIZE, drop_remainder=True)
        tf_ds = tf_ds.prefetch(tf.data.experimental.AUTOTUNE)
        self.tf_ds = tf_ds
        return tf_ds


    def build_tf_ds_val(self):
        logging.info('*** building tf.dataset (val) ***')

        def gen():
            for input_text, target_text in zip(self.val_q, self.val_a):
                input_token_dic = self.tokenizer(input_text,
                                                 truncation=True, max_length=512, return_tensors="tf")

                if len(input_token_dic['input_ids']) > self.config.MAX_LENGTH:
                    input_token_dic['input_ids'] = input_token_dic['input_ids'][:, -
                                                                                self.config.MAX_LENGTH:]
                    input_token_dic['attention_mask'] = input_token_dic['attention_mask'][:, -
                                                                                          self.config.MAX_LENGTH:]
                    input_token_dic['token_type_ids'] = input_token_dic['token_type_ids'][:, -
                                                                                          self.config.MAX_LENGTH:]
                else:
                    input_token_dic = self.tokenizer(input_text, padding='max_length',
                                                        truncation=True, max_length=self.config.MAX_LENGTH, return_tensors="tf")

                toot = KiriDataset.STR + target_text
                idxs = np.zeros((self.config.MAX_CHAR_LEN + 1,), dtype=int)
                for i2 in range(min([self.config.MAX_CHAR_LEN + 1, len(toot)])):
                    if toot[i2] in self.char_idx:
                        idxs[i2] = self.char_idx[toot[i2]]
                    else:
                        idxs[i2] = self.char_idx[KiriDataset.UNK]
                        # idxs[i2] = random.randrange(3, self.char_size)

                yield ((input_token_dic['input_ids'][0], input_token_dic['attention_mask'][0], idxs[:-1]), idxs[1:])

        if len(self.lines_a) == 0:
            self.read_input_data()
        tf_ds = tf.data.Dataset.from_generator(
            gen,
            output_signature=(
                (
                    tf.TensorSpec(
                        shape=(self.config.MAX_LENGTH,), dtype=tf.int16),
                    tf.TensorSpec(
                        shape=(self.config.MAX_LENGTH,), dtype=tf.int16),
                    tf.TensorSpec(
                        shape=(self.config.MAX_CHAR_LEN,), dtype=tf.int16),
                ),
                tf.TensorSpec(
                    shape=(self.config.MAX_CHAR_LEN,), dtype=tf.int16),
            )
        )
        tf_ds = tf_ds.batch(self.config.BATCH_SIZE, drop_remainder=True)
        tf_ds = tf_ds.prefetch(tf.data.experimental.AUTOTUNE)
        self.tf_ds_val = tf_ds
        return tf_ds
