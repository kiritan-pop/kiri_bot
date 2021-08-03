# -*- coding: utf-8 -*-

import logging
import tensorflow as tf
import numpy as np

logging.basicConfig(level=logging.INFO)

class KiriDataset:
    MU = "🧪"       # 無
    STR = "🦷"      # 始まりマーク
    def __init__(self, tokenizer, config) -> None:
        logging.info('*** read data ***')
        self.tokenizer = tokenizer
        self.config = config
        # 使用する文字種
        wl_chars = list(open(config.WL_PATH).read())
        wl_chars = [c for c in wl_chars if c not in [KiriDataset.MU, KiriDataset.STR]]
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

    def read_input_data(self):
        with open(self.config.DATA_FILE_PATH, 'r') as f:
            lines = [l.strip() for l in f.readlines()] #[:20000]

        for i in range(len(lines) - self.config.SUM_LINES_SIZE):
            self.lines_q.append(
                "\n".join(lines[i:i + self.config.SUM_LINES_SIZE]))
            self.lines_a.append(lines[i + self.config.SUM_LINES_SIZE])


    def tokenize(self):
        if len(self.lines_q) == 0:
            self.read_input_data()
        self.input_encoded_dict = self.tokenizer(self.lines_q, padding='max_length', truncation=True, max_length=self.config.MAX_LENGTH)


    def read_encoder_output(self):
        self.encoder_output = np.load(self.config.ENCODER_OUTPUT_PATH)


    def _gen(self):
        for input_ids, input_mask, toot_org in zip(self.input_encoded_dict['input_ids'], self.input_encoded_dict['attention_mask'], self.lines_a):
            toot = KiriDataset.STR + toot_org
            idxs = np.zeros((self.config.MAX_CHAR_LEN + 1,), dtype=int)
            for i in range( min([self.config.MAX_CHAR_LEN + 1, len(toot)])):
                idxs[i] = self.char_idx[toot[i]]
            yield ((input_ids, input_mask, idxs[:-1]),
                    tf.one_hot(idxs[1:], self.char_size, dtype=tf.uint8))


    def build_tf_ds(self):
        if self.input_encoded_dict is None:
            self.tokenize()
        tf_ds = tf.data.Dataset.from_generator(
                    self._gen,
                    output_signature=(
                        (
                            tf.TensorSpec(shape=(self.config.MAX_LENGTH,), dtype=tf.int16),
                            tf.TensorSpec(shape=(self.config.MAX_LENGTH,), dtype=tf.uint8),
                            tf.TensorSpec(shape=(self.config.MAX_CHAR_LEN,), dtype=tf.int16),
                        ),
                        tf.TensorSpec(shape=(self.config.MAX_CHAR_LEN, self.char_size), dtype=tf.uint8),
                    )
        )
        tf_ds = tf_ds.shuffle(self.config.BATCH_SIZE*2)
        tf_ds = tf_ds.batch(self.config.BATCH_SIZE, drop_remainder=True)
        tf_ds = tf_ds.prefetch(tf.data.experimental.AUTOTUNE)
        self.tf_ds = tf_ds


    def _gen4decoder(self):
        for i1 in range(len(self.lines_a)):
        # for input_ids, input_mask, toot_org in zip(self.input_encoded_dict['input_ids'], self.input_encoded_dict['attention_mask'], self.lines_a):
            toot = KiriDataset.STR + self.lines_a[i1]
            idxs = np.zeros((self.config.MAX_CHAR_LEN + 1,), dtype=int)
            for i2 in range( min([self.config.MAX_CHAR_LEN + 1, len(toot)])):
                idxs[i2] = self.char_idx[toot[i2]]
            yield ((self.encoder_output[i1,:], idxs[:-1]),
                    tf.one_hot(idxs[1:], self.char_size, dtype=tf.uint8))


    def build_tf_ds4decoder(self):
        if len(self.lines_a) == 0:
            self.read_input_data()
        if self.encoder_output is None:
            self.read_encoder_output()
        print(f"len(self.lines_a)={len(self.lines_a)}")
        print(f"self.encoder_output.shape={self.encoder_output.shape}")
        tf_ds = tf.data.Dataset.from_generator(
                    self._gen4decoder,
                    output_signature=(
                        (
                            tf.TensorSpec(shape=(self.encoder_output.shape[1],), dtype=tf.float32),
                            tf.TensorSpec(shape=(self.config.MAX_CHAR_LEN,), dtype=tf.int16),
                        ),
                        tf.TensorSpec(shape=(self.config.MAX_CHAR_LEN, self.char_size), dtype=tf.uint8),
                    )
        )
        tf_ds = tf_ds.shuffle(self.config.BATCH_SIZE*2)
        tf_ds = tf_ds.batch(self.config.BATCH_SIZE, drop_remainder=True)
        tf_ds = tf_ds.prefetch(tf.data.experimental.AUTOTUNE)
        self.tf_ds = tf_ds
