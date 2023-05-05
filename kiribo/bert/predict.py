# -*- coding: utf-8 -*-

import logging
# import onnxruntime as ort
from deepsparse import compile_model
# import openvino.runtime as ov

import logging

import numpy as np
from transformers import AutoTokenizer
import sentencepiece as spm

from .config import KiriConfig

logging.basicConfig(level=logging.INFO)

# deepsparse :体感onnxより速い
engine = compile_model(KiriConfig.SAVE_PATH, batch_size=1)
tokenizer = AutoTokenizer.from_pretrained(KiriConfig.MODEL_NAME)
sp = spm.SentencePieceProcessor(model_file=KiriConfig.SPM_MODEL)


def gen_text(
        input_text: str,
        temperature=0.75,
        topk=500,
        topp=0.9,
):

    input_token_dic = tokenizer(input_text,
                                truncation=True, max_length=512, return_tensors='pt')

    if input_token_dic['input_ids'].shape[1] > KiriConfig.MAX_LENGTH:
        input_token_dic['input_ids'] = input_token_dic['input_ids'][:, -
                                                                    KiriConfig.MAX_LENGTH:]
        input_token_dic['attention_mask'] = input_token_dic['attention_mask'][:, -
                                                                              KiriConfig.MAX_LENGTH:]
        input_token_dic['token_type_ids'] = input_token_dic['token_type_ids'][:, -
                                                                              KiriConfig.MAX_LENGTH:]
    else:
        input_token_dic = tokenizer(input_text, padding='max_length',
                                    truncation=True, max_length=KiriConfig.MAX_LENGTH, return_tensors='pt')

    output_ids = np.full((1, KiriConfig.MAX_CHAR_LEN + 1), sp.pad_id())
    output_ids[0, 0] = sp.bos_id()
    generated_text = ""

    for cur in range(1, KiriConfig.MAX_CHAR_LEN + 1):
        preds = engine.run(
            [input_token_dic['input_ids'].numpy(), output_ids[:, :-1]])[0]
        preds = softmax(preds[0])
        next_id = int(
            sample(preds[cur - 1], temperature=temperature, topk=topk, topp=topp))
        output_ids[0, cur] = next_id
        tmp_char = sp.decode_ids([next_id])
        tmp_char = tmp_char.replace("<br>", "\n")
        generated_text += tmp_char
        print(f"{tmp_char}", end="", flush=True)

        if next_id == sp.pad_id():
            break

    print("")
    return generated_text


def sample(preds, temperature=1.0, topk=None, topp=1.0):
    # helper function to sample an index from a probability array
    preds = np.asarray(preds).astype('float64')

    if topp < 1.0:
        left = 0
        right = preds.shape[-1]
        mid = preds.shape[-1]
        while left <= right:
            mid = (left + right)//2
            if mid == 0:
                mid = 1
                break
            p = preds[preds.argsort()[::-1][:mid]].sum()
            if p > topp:
                right = mid - 1
            elif p == topp:
                break
            else:
                left = mid + 1

        preds[preds.argsort()[::-1][mid:]] = 0

    if topk:
        indices = np.argpartition(-preds, topk)[topk:]
        for i in indices:
            preds[i] = 0.0
    with np.errstate(divide='ignore'):
        preds = np.log(preds) / temperature
    exp_preds = np.exp(preds)
    preds = exp_preds / np.sum(exp_preds)
    probas = np.random.multinomial(1, preds, 1)
    return np.argmax(probas)


def softmax(x):
    f = np.exp(x)/np.sum(np.exp(x), axis=1, keepdims=True)
    return f
