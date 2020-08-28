#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import MeCab as mc
import numpy as np
import re
import os
from argparse import ArgumentParser

# きりぼコンフィグ
from kiribo.config import EMOJI_PATH, NAME_DIC_PATH, ID_DIC_PATH, NICODIC_PATH, IPADIC_PATH

eos_list = []
if os.path.exists(EMOJI_PATH):
    with open(EMOJI_PATH, 'r') as f:
        eos_list = list(f.read())
    
#eos_list.extend(["!","♡","♪","、","。","\.","？","\?","！","\n","w","ｗ","」","）","「","（","＊","　"])
#eos_list.extend(["!","♡","♪","、","。","\.","？","\?","！","\n","w","ｗ","＊","　"])
eos_list.extend(["!","♡","♪","。","？","?","！","\n","w","ｗ","＊","*",",","　",":",";","：","；","…","・・・","...","〜"])
eos_list.extend(["♥","★","☆","■","□","◆","◇","▲","△","▼","▽","●","○","(_)"])

m = mc.Tagger(f"-Owakati -d {IPADIC_PATH} -u {NAME_DIC_PATH},{ID_DIC_PATH},{NICODIC_PATH}")

def parser():
    usage = 'Usage:python3 b_summary.py [-t <FILE.txt>] [--help]'
    parser = ArgumentParser(usage=usage)
    parser.add_argument('-t','--text',dest='input_text',help='text file' )

    args = parser.parse_args()
    if args.input_text:
        return '{}'.format(text_input(args.input_text))

def mecab_senter(text):
    words = m.parse(text).split()
    sentences = []
    sentence = []
    for word in words:
        sentence.append(word)
        if word in  eos_list:
            sentences.append(sentence)
            sentence = []

    return sentences

def get_freqdict(sentences):
    freqdict = {}
    N = 0
    for sentence in sentences:
        for word in sentence:
            freqdict.setdefault(word, 0.)
            freqdict[word] += 1
            N += 1
    return freqdict

def score(sentence, freqdict):
    return np.sum([np.log(freqdict[word]) for word in sentence]) / len(sentence)

def direct_proportion(i, n):
    return float(n-i+1)/n

def inverse_proportion(i, n):
    return 1.0 / i

def geometric_sequence(i, n):
    return 0.5 ** (i-1)

def inverse_entropy(p):
    if p == 1.0 or 0.0:
        return 1.0
    return 1-(-p*np.log(p) - (1-p)*np.log(1-p))

def inverse_entropy_proportion(i, n):
    p = i / n
    return inverse_entropy(p)

def summarize(text, limit=50, lmtpcs=5, **options):
    """
    text: target text
    limit: summary length limit
    option:
    -m: summarization mode
        0: basic summarization model
        1: using word position feature
    -f: feature function
        0: direct proportion (DP)
        1: inverse proportion (IP)
        2: Geometric sequence (GS)
        3: Binary function (BF)
        4: Inverse entropy
    """
    text = re.sub(r'焦がしにんにくのマー油と葱油が香るザ★チャーハン600g','炒飯',text)
    text = re.sub(r'\n','(_)',text) #Mecabで改行がなくなるので、一時的に置き換える。
    sentences = mecab_senter(text)
    freqdict = get_freqdict(sentences)
    if options["m"] == 0:
        scores = [score(sentence, freqdict) for sentence in sentences]
    if options["m"] == 1:
        if options["f"] == 0:
            word_features = direct_proportion
        elif options["f"] == 1:
            word_features = inverse_proportion
        elif options["f"] == 2:
            word_features = geometric_sequence
        elif options["f"] == 4:
            word_features = inverse_entropy_proportion

        scores = []
        feature_dict = {}
        for sentence in sentences:
            sent_score = 0.0
            for word in sentence:
                feature_dict.setdefault(word, 0.0)
                feature_dict[word] += 1
                sent_score += np.log(freqdict[word]) * word_features(feature_dict[word], freqdict[word])
            sent_score /= len(sentence)
            scores.append(sent_score)

    topics = []
    length = 0
    for index in sorted(range(len(scores)), key=lambda k: scores[k], reverse=True):
        if len(topics) > lmtpcs: break
        if length > limit: break
        if len(sentences[index]) > 5:
            length += len(sentences[index])
            topics.append(index)
    topics = sorted(topics)
    #print(topics)
    return "＊" + "\n＊".join(["".join(sentences[topic]).replace("。","").replace("、","").replace("(_)","") for topic in topics])


def text_input(text):
    text_title = text
    #text_text = open(text_title).read().replace('\n','。').replace('\r','')
    text_text = re.sub("[^。]\n", "。", re.sub("[「」]","", open(text_title).read()))

    #summry_text = text_output(text_title,text_text)
    print("basic summarization model")
    print(summarize(text_text, m=0))
    print("#####################################")
    print("using word position feature and direct proportion")
    print(summarize(text_text,m=1,f=0))
    print("#####################################")
    print("using word position feature and inverse proportion")
    print(summarize(text_text, m=1, f=1))
    print("#####################################")
    print("using word position feature and Geometric sequence")
    print(summarize(text_text, m=1, f=2))
    print("#################################################")
    return "終了"


if __name__ == '__main__':
    result = parser()
    print(result)
