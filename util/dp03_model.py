# -*- coding: utf-8 -*-

from gensim.models import word2vec
import logging
import sys

logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)

sentences = word2vec.LineSentence(sys.argv[1])
model = word2vec.Word2Vec(sentences,
                          sg=0,
                          size=80,
                          min_count=20,
                          window=20,
                          #negative=3,
                          workers=11,
                          #iter=10,
                          hs=1)
model.save(sys.argv[2])
