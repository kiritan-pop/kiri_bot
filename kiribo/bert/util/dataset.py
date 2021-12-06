# -*- coding: utf-8 -*-

import os
import json
import random
import logging
import tensorflow as tf
import numpy as np

logging.basicConfig(level=logging.INFO)

class KiriDataset:
    MU = "🧪"       # 無 padding
    STR = "🦷"      # 始まりマーク
    def __init__(self, tokenizer, config, encoder_model=None) -> None:
        logging.info('*** data initializing***')
        self.tokenizer = tokenizer
        self.config = config
        self.encoder_model = encoder_model
        # 使用する文字種
        # wl_chars = list(open(config.WL_PATH).read())
        cnt_dict = {}
        for line in open(self.config.DATA_FILE_PATH, 'r'):
            for c in list(line):
                if c in cnt_dict:
                    cnt_dict[c] += 1
                else:
                    cnt_dict[c] = 1

        sorted_dict = {}
        for k, v in sorted(cnt_dict.items(), key=lambda x: -x[1]):
            sorted_dict[k] = v
        wl_chars = list(sorted_dict.keys())
        print(f"wl_chars:{len(wl_chars)}")

        wl_chars = [c for c in wl_chars if c not in [KiriDataset.MU, KiriDataset.STR]]
        with open(config.WL_PATH, "w") as f:
            f.writelines(wl_chars)

        wl_chars.insert(0, KiriDataset.STR)
        wl_chars.insert(0, KiriDataset.MU)
        self.char_size = len(wl_chars)
        self.idx_char = {i:c for i,c in enumerate(wl_chars)}
        self.char_idx = {c:i for i,c in enumerate(wl_chars)}

        self.lines_q = []
        self.lines_a = []
        self.input_encoded_dict = None
        self.encoder_output = None
        self.tf_ds = None
        self.train_data_num_list = []

    def read_input_data(self):
        logging.info('*** reading data ***')
        with open(self.config.DATA_FILE_PATH, 'r') as f:
            lines = [l.strip() for l in f.readlines()] #[:20000]

        for size in range(3, self.config.SUM_LINES_SIZE + 1):
            for i in range(len(lines) - size):
                self.lines_q.append(
                    self.config.SEP.join(lines[i:i + size]))
                self.lines_a.append(lines[i + size])

        logging.info(f'*** data len = {len(self.lines_a)}***')
        with open("data/tmp.txt", 'w') as f:
            for q, a in zip(self.lines_q, self.lines_a):
                f.write(q + ">>>>>" + a + "\n")

    def build_tf_ds(self):
        logging.info('*** building tf.dataset ***')

        def gen():
            if self.config.STEPS_PER_EPOCH > 0:
                if len(self.train_data_num_list) < self.config.STEPS_PER_EPOCH*self.config.BATCH_SIZE:
                    self.train_data_num_list = list(range(len(self.lines_q)))

                nums = random.sample(self.train_data_num_list, min(
                    [self.config.STEPS_PER_EPOCH*self.config.BATCH_SIZE, len(self.train_data_num_list)]))
                self.train_data_num_list = list(
                    set(self.train_data_num_list) - set(nums))
            else:
                nums = list(range(len(self.lines_a)))
                random.shuffle(nums)
            for i1 in nums:
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
                    idxs[i2] = self.char_idx[toot[i2]]
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
        # tf_ds = tf_ds.cache()
        # tf_ds = tf_ds.shuffle(5000)
        tf_ds = tf_ds.batch(self.config.BATCH_SIZE, drop_remainder=True)
        tf_ds = tf_ds.prefetch(tf.data.experimental.AUTOTUNE)
        self.tf_ds = tf_ds
