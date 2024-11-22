# -*- coding: utf-8 -*-

import logging
# from deepsparse import compile_model # quantizeしたら使えない
from onnxruntime import InferenceSession

import logging

import numpy as np
from transformers import AutoTokenizer
import sentencepiece as spm

from .config import KiriConfig

logging.basicConfig(level=logging.INFO)

session = InferenceSession(KiriConfig.SAVE_PATH)
tokenizer = AutoTokenizer.from_pretrained(KiriConfig.MODEL_NAME)
sp = spm.SentencePieceProcessor(model_file=KiriConfig.SPM_MODEL)


def gen_text(
        input_text_list: list,
        temperature=0.75,
        topk=500,
        topp=0.8,
):

    input_text = tokenizer.sep_token.join(input_text_list)
    input_token_dic = tokenizer(input_text,
                                truncation=True, max_length=512, return_tensors='np')

    if input_token_dic['input_ids'].shape[1] > KiriConfig.MAX_LENGTH:
        input_token_dic['input_ids'] = input_token_dic['input_ids'][:, -
                                                                    KiriConfig.MAX_LENGTH:]
        input_token_dic['attention_mask'] = input_token_dic['attention_mask'][:, -
                                                                              KiriConfig.MAX_LENGTH:]
        # input_token_dic['token_type_ids'] = input_token_dic['token_type_ids'][:, -
        #                                                                       KiriConfig.MAX_LENGTH:]
    else:
        input_token_dic = tokenizer(input_text, padding='max_length',
                                    truncation=True, max_length=KiriConfig.MAX_LENGTH, return_tensors='np')

    output_ids = np.full((1, KiriConfig.MAX_CHAR_LEN + 1), sp.pad_id())
    output_ids[0, 0] = sp.bos_id()
    output_ids_list = []

    for cur in range(1, KiriConfig.MAX_CHAR_LEN + 1):
        preds = session.run(None, dict(enc_input=input_token_dic['input_ids'], dec_input=output_ids[:, :-1]))[0]
        preds = softmax(preds[0])
        next_id = int(
            sample(preds[cur - 1], temperature=temperature, topk=topk, topp=topp))

        if next_id in [sp.pad_id(), sp.eos_id()]:
            break

        output_ids[0, cur] = next_id
        output_ids_list.append(next_id)

    generated_text = sp.decode_ids(output_ids_list)
    generated_text = generated_text.replace("<br>", "\n")
    generated_text = generated_text.replace("⁇", "")
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
