# -*- coding: utf-8 -*-

import logging
import tensorflow as tf
import numpy as np
from transformers import AutoTokenizer
NN = "[SEP]"

def gen_text(
        encoder_model: tf.keras.Model, 
        decoder_model: tf.keras.Model, 
        tokenizer: AutoTokenizer, 
        config, 
        dataset, 
        input_text: str, 
        temperature=0.5, 
        topk=300
        ):
        
    logging.info('*** Generating text after Epoch ***')
    input_token_dic = tokenizer(input_text,
                                truncation=True, max_length=512, return_tensors='tf')

    if len(input_token_dic['input_ids']) > config.MAX_LENGTH:
        input_token_dic['input_ids'] = input_token_dic['input_ids'][:, -config.MAX_LENGTH:]
        input_token_dic['attention_mask'] = input_token_dic['attention_mask'][:, -config.MAX_LENGTH:]
        input_token_dic['token_type_ids'] = input_token_dic['token_type_ids'][:, -config.MAX_LENGTH:]
    else:
        input_token_dic = tokenizer(input_text, padding='max_length',
                                    truncation=True, max_length=config.MAX_LENGTH, return_tensors='tf')
    encoder_output = encoder_model.predict_on_batch(
        (input_token_dic['input_ids'], input_token_dic['attention_mask']))

    output_ids = np.full((1, config.MAX_CHAR_LEN + 1),
                         dataset.char_idx[dataset.MU])
    output_ids[0,0] = dataset.char_idx[dataset.STR]
    generated_text = ""
    for cur in range(1, config.MAX_CHAR_LEN + 1):
        preds = decoder_model.predict_on_batch((encoder_output, output_ids[:,:-1]))

        temp_ids = []
        for pidx in range(config.MAX_CHAR_LEN):
            temp_ids.append( int(sample(preds[0][pidx], temperature=temperature, topk=topk)))

        next_id = temp_ids[cur - 1]
        output_ids[0, cur] = next_id
        generated_text += dataset.idx_char[next_id]
        if next_id == dataset.char_idx[dataset.MU]:
            break

    logging.info(f'generated_text={generated_text}')

    return generated_text

def sample(preds, temperature=1.0, topk=None):
    # helper function to sample an index from a probability array
    preds = np.asarray(preds).astype('float64')
    if topk:
        indices = np.argpartition(-preds, topk)[topk:]
        for i in indices:
            preds[i] = 0.0
    preds = np.log(preds) / temperature
    exp_preds = np.exp(preds)
    preds = exp_preds / np.sum(exp_preds)
    probas = np.random.multinomial(1, preds, 1)
    return np.argmax(probas)
