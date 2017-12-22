# -*- coding: utf-8 -*-

import os.path
import sqlite3
import random
import sys
BEGIN = u"__BEGIN_SENTENCE__"
END = u"__END_SENTENCE__"

class GenerateText(object):
    def __init__(self,num=3):
        self.n = num

    def generate(self,switch):
        db_path = "db/" + switch + ".db"
        if not os.path.exists(db_path):
            con = sqlite3.connect('db/chain.db')
        else:
            con = sqlite3.connect(db_path)

        con.row_factory = sqlite3.Row
        # 最終的にできる文章
        generated_text = ""
        # 指定の数だけ作成する
        for i in range(self.n):
            text = self._generate_sentence(con,switch)
            generated_text += text
        # DBクローズ
        con.close()
        return generated_text

    def _generate_sentence(self, con, switch):
        # 生成文章のリスト
        morphemes = []
        # はじまりを取得
        first_triplet = self._get_first_triplet(con)
        morphemes.append(first_triplet[1])
        morphemes.append(first_triplet[2])
        # 文章を紡いでいく
        while morphemes[-1] != END:
            prefix1 = morphemes[-2]
            prefix2 = morphemes[-1]
            triplet = self._get_triplet(con, prefix1, prefix2)
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
            result = "".join(morphemes[:-1]) + "\n"
        return result

    def _get_chain_from_DB(self, con, prefixes):
        # ベースとなるSQL
        sql = u"select prefix1, prefix2, suffix, freq from chain_freqs where prefix1 = ?"
        # prefixが2つなら条件に加える
        if len(prefixes) == 2:
            sql += u" and prefix2 = ?"
        # 結果
        result = []
        # DBから取得
        cursor = con.execute(sql, prefixes)
        for row in cursor:
            result.append(dict(row))
        return result

    def _get_first_triplet(self, con):
        # BEGINをprefix1としてチェーンを取得
        prefixes = (BEGIN,)
        # チェーン情報を取得
        chains = self._get_chain_from_DB(con, prefixes)
        # 取得したチェーンから、確率的に1つ選ぶ
        triplet = self._get_probable_triplet(chains)
        return (triplet["prefix1"], triplet["prefix2"], triplet["suffix"])

    def _get_triplet(self, con, prefix1, prefix2):
        # BEGINをprefix1としてチェーンを取得
        prefixes = (prefix1, prefix2)
        # チェーン情報を取得
        chains = self._get_chain_from_DB(con, prefixes)
        # 取得したチェーンから、確率的に1つ選ぶ
        triplet = self._get_probable_triplet(chains)
        return (triplet["prefix1"], triplet["prefix2"], triplet["suffix"])

    def _get_probable_triplet(self, chains):
        # 確率配列
        probability = []
        # 確率に合うように、インデックスを入れる
        for (index, chain) in enumerate(chains):
            for j in range(chain["freq"]):
                probability.append(index)
        # ランダムに1つを選ぶ
        chain_index = random.choice(probability)
        return chains[chain_index]

if __name__ == '__main__':
    param = sys.argv
    if (len(param) != 2):
        print ("Usage: $ python " + param[0] + " number")
        quit()

    generator = GenerateText(int(param[1]))
    gen_txt = generator.generate("sousi")
    print (gen_txt)

    gen_txt = generator.generate("poke")
    print (gen_txt)

    gen_txt = generator.generate("kiritan")
    print (gen_txt)
