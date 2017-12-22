# -*- coding: utf-8 -*-

from gensim.models import word2vec
import logging
import sys
from gensim.models.doc2vec import Doc2Vec
from gensim.models.doc2vec import TaggedDocument

logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)

#tag_model   = word2vec.Word2Vec.load(sys.argv[1])

# 空のリストを作成（学習データとなる各文書を格納）

f = open(sys.argv[1])
tags = f.readlines() # 1行毎にファイル終端まで全て読む(改行文字も含まれる)
f.close()

f = open(sys.argv[2])
lines = f.readlines() # 1行毎にファイル終端まで全て読む(改行文字も含まれる)
f.close()

training_docs = []
sentents = []
sent_id = 0
for (line,tag) in zip(lines,tags):
    # 各文書を表すTaggedDocumentクラスのインスタンスを作成
    # words：文書に含まれる単語のリスト（単語の重複あり）
    # tags：文書の識別子（リストで指定．1つの文書に複数のタグを付与できる）
    sentents.append(line)
    sent = TaggedDocument(words=line.split(), tags=tag.split())
    # 各TaggedDocumentをリストに格納
    training_docs.append(sent)
    sent_id += 1

# 学習実行（パラメータを調整可能）
# documents:学習データ（TaggedDocumentのリスト）
# min_count=1:最低1回出現した単語を学習に使用する
# 学習モデル=DBOW（デフォルトはdm=1:学習モデル=DM）
model = Doc2Vec(documents=training_docs,
                size=300,
                window=5,
                alpha=0.0025,
                min_alpha=.0001,
                min_count=8,
                sample=1e-6,
                workers=12,
                iter=600,
                negative=5,
                hs=1,
                dm=1)
model.save(sys.argv[3])
