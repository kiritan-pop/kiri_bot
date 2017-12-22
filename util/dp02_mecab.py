# -*- coding: utf-8 -*-

import MeCab
import sys,re

#tagger = MeCab.Tagger('-F\s%f[6] -U\s%m -E\\n')
tagger = MeCab.Tagger('-Owakati -d /usr/lib/mecab/dic/mecab-ipadic-neologd -u name.dic,id.dic,nicodic.dic')

fi = open(sys.argv[1], 'r')
fo = open(sys.argv[2], 'w')

pat1 = re.compile(u' ([!-~ぁ-んァ-ン] )+|^([!-~ぁ-んァ-ン] )+| [!-~ぁ-んァ-ン]$')  #[!-~0-9a-zA-Zぁ-んァ-ン０-９ａ-ｚ]
pat2 = re.compile(u'\n\n|[[|]]|=【】『』《》「」〈〉｛｝［］（）≪≫｢｣{}<>()<>‘’〔〕')  #wikipedia 用
line = fi.readline()
while line:
    result = tagger.parse(line)
#    fo.write(result[1:]) # skip first \s
    fo.write(pat2.sub(" ",pat1.sub(" ",pat1.sub(" ", result)))) # skip first \s
    line = fi.readline()

fi.close()
fo.close()
