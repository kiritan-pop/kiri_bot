# -*- coding: utf-8 -*-

import os
import logging
from onnxruntime import InferenceSession
import numpy as np
from transformers import T5Tokenizer
from .config import KiriConfig

logging.basicConfig(level=logging.INFO)

# 
session = InferenceSession(KiriConfig.QUANTIZED_MODEL_PATH)
tokenizer = T5Tokenizer.from_pretrained(os.path.dirname(KiriConfig.QUANTIZED_MODEL_PATH), use_fast=True)

black_words = ["きりぼ占って", "こらきりぼ"]
# ブラックワードをトークン化（順序を保持）
black_word_sequences = [tokenizer.encode(word) for word in black_words]


def gen_text(
        input_text_list: list,
        temperature=0.75, 
        topk=500,
        topp=0.8,
        repetition_penalty=1.2,  # 繰り返しペナルティ
        black_word_penalty=1.5,  # ブラックワードのペナルティ係数
        ):
    
    input_text = KiriConfig.SEP.join(input_text_list)
    input_token_dic = tokenizer(input_text,
                                truncation=True, max_length=KiriConfig.MAX_INPUT_LENGTH, return_tensors='np')
    
    # T5 の場合、生成開始時には decoder_start_token_id を用います
    # 多くの場合、T5では pad_token_id が decoder_start_token_id として利用されるか、明示的に設定する必要があります
    decoder_start_token_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id
    
    output_ids = np.full((1, KiriConfig.MAX_OUTPUT_LENGTH + 1), tokenizer.pad_token_type_id)
    output_ids[0, 0] = decoder_start_token_id
    output_ids_list = []
    
    for cur in range(1, KiriConfig.MAX_OUTPUT_LENGTH + 1):
        preds = session.run(["output"], dict(
            input_ids=input_token_dic['input_ids'],
            attention_mask=input_token_dic['attention_mask'],
            decoder_input_ids=output_ids[:, :-1]
        ))[0]
        preds = softmax(preds[0])
    
        # 繰り返しペナルティの適用
        for prev_id in output_ids_list:
            if preds[cur - 1, prev_id] > 0:  # 確率が正の場合のみ調整
                preds[cur - 1, prev_id] /= repetition_penalty

        # ブラックワードシーケンスのチェック（改良版）
        for sequence in black_word_sequences:
            # 現在の出力の末尾とブラックワードシーケンスの共通の接頭辞の長さを求める
            match_len = 0
            max_possible = min(len(sequence), len(output_ids_list))
            for j in range(1, max_possible + 1):
                # 出力の最後 j トークンとブラックワードの先頭 j トークンが一致するか確認
                if output_ids_list[-j:] == sequence[:j]:
                    match_len = j
                else:
                    break
            # もし部分一致していて、まだシーケンスが完全には生成されていなければ、
            # 次に続くトークン候補（ブラックワードシーケンスの次のトークン）にペナルティを適用
            if match_len < len(sequence):
                next_token = sequence[match_len]
                # 生成済みの一致の長さに応じ、ペナルティを累乗で強化（例：1トークン一致なら black_word_penalty、2トークン一致なら black_word_penalty^2、…）
                penalty_factor = black_word_penalty ** match_len
                if preds[cur - 1, next_token] > 0:
                    preds[cur - 1, next_token] /= penalty_factor
        
        # 次のトークンをサンプリング
        next_id = int(sample(preds[cur - 1], temperature=temperature, topk=topk, topp=topp))
        if next_id in [tokenizer.eos_token_id]:
            print("\n")
            break
        output_ids[0, cur] = next_id
        output_ids_list.append(next_id)
        # tmp_char = tokenizer.decode(next_id)
        # tmp_char = tmp_char.replace("<br>", "\n")
        # print(f"{tmp_char}", end="", flush=True)

    generated_text = tokenizer.decode(output_ids_list)
    generated_text = generated_text.replace("<br>", "\n")
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
    f = np.exp(x)/np.sum(np.exp(x), axis = 1, keepdims = True)
    return f
