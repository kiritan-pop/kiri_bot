# -*- coding: utf-8 -*-

import os
import logging
import tensorflow as tf
from transformers import AutoTokenizer
from .model.encoder_decoder import build_encoder, build_decoder
from .util.predict import gen_text as _gen_text
from .util.dataset import KiriDataset
from .config import KiriConfig

logging.basicConfig(level=logging.INFO)


logging.info('*** Initializing ***')
tokenizer = AutoTokenizer.from_pretrained(KiriConfig.MODEL_NAME)
dataset = KiriDataset(tokenizer=tokenizer, config=KiriConfig)
encoder_model = build_encoder(
            input_length=KiriConfig.MAX_LENGTH,
            model_name=KiriConfig.MODEL_NAME,
)
decoder_model = build_decoder(
            vocab_size = dataset.char_size,
            hopping_num = KiriConfig.HOPPING_NUM,
            head_num = KiriConfig.HEAD_NUM,
            hidden_dim = KiriConfig.HIDDEN_DIM,
            dropout_rate = KiriConfig.DROPOUT_RATE,
            target_length=KiriConfig.MAX_CHAR_LEN,
            encoder_output_dim = 768,
)

latest = tf.train.latest_checkpoint(os.path.dirname(KiriConfig.SAVE_PATH))
if latest:
    logging.info(f'*** load model-weights {latest} ***')
    decoder_model.load_weights(latest)
else:
    raise Exception("No trained model")


def gen_text(
        input_text,
        temperature=1.0,
        topk=1000,
    ):
    return _gen_text(
            encoder_model=encoder_model, 
            decoder_model=decoder_model, 
            tokenizer=tokenizer, 
            config=KiriConfig,
            dataset=dataset, 
            input_text=input_text,
            temperature=temperature,
            topk=topk,
        )[:-1]


if __name__ == '__main__':
    print(gen_text(input_text=input(">>").strip()))