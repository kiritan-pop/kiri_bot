# -*- coding: utf-8 -*-

import os.path
import sqlite3
import random
import sys
from pytz import timezone
from datetime import datetime,timedelta
BEGIN = u"__BEGIN_SENTENCE__"
END = u"__END_SENTENCE__"

class GenerateText(object):
    def __init__(self,num=3):
        self.n = num

    def _print_log(self,text):
        return
        #with open('gentext.log', 'a') as f:
        #    f.write(text+'\n')

    def generate(self,switch):
        self._print_log('@@@generate : %s'%switch)
        str_time = datetime.now(timezone('Asia/Tokyo'))
        db_path = "db/" + switch + ".db"
        if not os.path.exists(db_path):
            con = sqlite3.connect('db/chain.db')
        else:
            con = sqlite3.connect(db_path,check_same_thread=False)

        con.row_factory = sqlite3.Row
        cur = con.cursor()
        # 最終的にできる文章
        generated_text = ""
        # 指定の数だけ作成する
        for i in range(self.n):
            text = self._generate_sentence(cur,switch)
            generated_text += text  + "\n"
        # DBクローズ
        con.close()
        end_time = datetime.now(timezone('Asia/Tokyo'))
        dif_time = end_time - str_time
        self._print_log('@@@generate : %s'%dif_time)
        return generated_text[0:-1]

    def _generate_sentence(self, cur, switch):
        str_time = datetime.now(timezone('Asia/Tokyo'))
        # 生成文章のリスト
        morphemes = []
        # はじまりを取得
        first_triplet = self._get_first_triplet(cur)
        morphemes.append(first_triplet[1])
        morphemes.append(first_triplet[2])
        # 文章を紡いでいく
        while morphemes[-1] != END:
            prefix1 = morphemes[-2]
            prefix2 = morphemes[-1]
            triplet = self._get_triplet(cur, prefix1, prefix2)
            morphemes.append(triplet[2])
        # 連結
        if switch == "poke":
            result = ""
            #print(morphemes)
            for morpheme in morphemes[:-1]:
                #print(morpheme)
                if len(morpheme) < 4:
                    result += morpheme
                else:
                    result += morpheme + " "
            result = result[:-1]
            #末尾に句読点
            if result[-1:1] == "。":
                pass
            else:
                result += "。"
        else:
            result = "".join(morphemes[:-1])

        end_time = datetime.now(timezone('Asia/Tokyo'))
        dif_time = end_time - str_time
        self._print_log('@@@_generate_sentence : %s'%dif_time)
        #print(result)
        return result

    def _get_chain_from_DB(self, cur, prefixes):
        str_time = datetime.now(timezone('Asia/Tokyo'))
        self._print_log('@@@_get_chain_from_DB str')
        # ベースとなるSQL
        sql = u"select prefix1, prefix2, suffix, freq from chain_freqs where prefix1 = ?"
        # prefixが2つなら条件に加える
        if len(prefixes) == 2:
            sql += u" and prefix2 = ?"
        # 結果
        result = []
        # DBから取得
        cur.execute(sql, prefixes)
        rows = cur.fetchall()
        for row in rows:
            #print(dict(row))
            result.append(dict(row))

        end_time = datetime.now(timezone('Asia/Tokyo'))
        dif_time = end_time - str_time
        self._print_log('@@@ rows=%d'%len(rows))
        self._print_log('@@@_get_chain_from_DB : %s'%dif_time)
        return result

    def _get_first_triplet(self, cur):
        str_time = datetime.now(timezone('Asia/Tokyo'))
        # BEGINをprefix1としてチェーンを取得
        prefixes = (BEGIN,)
        # チェーン情報を取得
        chains = self._get_chain_from_DB(cur, prefixes)
        # 取得したチェーンから、確率的に1つ選ぶ
        triplet = self._get_probable_triplet(chains)

        end_time = datetime.now(timezone('Asia/Tokyo'))
        dif_time = end_time - str_time
        self._print_log('@@@_get_first_triplet : %s'%dif_time)
        return (triplet["prefix1"], triplet["prefix2"], triplet["suffix"])

    def _get_triplet(self, cur, prefix1, prefix2):
        str_time = datetime.now(timezone('Asia/Tokyo'))
        # BEGINをprefix1としてチェーンを取得
        prefixes = (prefix1, prefix2)
        # チェーン情報を取得
        chains = self._get_chain_from_DB(cur, prefixes)
        # 取得したチェーンから、確率的に1つ選ぶ
        triplet = self._get_probable_triplet(chains)

        end_time = datetime.now(timezone('Asia/Tokyo'))
        dif_time = end_time - str_time
        self._print_log('@@@_get_triplet : %s'%dif_time)
        return (triplet["prefix1"], triplet["prefix2"], triplet["suffix"])

    def _get_probable_triplet(self, chains):
        str_time = datetime.now(timezone('Asia/Tokyo'))
        # 確率配列
        probability = []
        # 確率に合うように、インデックスを入れる
        for (index, chain) in enumerate(chains):
            for j in range(chain["freq"]):
                probability.append(index)
        # ランダムに1つを選ぶ
        chain_index = random.choice(probability)

        end_time = datetime.now(timezone('Asia/Tokyo'))
        dif_time = end_time - str_time
        self._print_log('@@@_get_probable_triplet : %s'%dif_time)
        return chains[chain_index]

if __name__ == '__main__':
    param = sys.argv
    if (len(param) != 3):
        print ("Usage: $ python " + param[0] + " number")
        quit()

    generator = GenerateText(int(param[1]))
    gen_txt = generator.generate(param[2])
    print (gen_txt)
