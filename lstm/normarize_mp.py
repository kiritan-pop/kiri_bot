# coding: utf-8

import sys
import io,re,random
import unicodedata
from multiprocessing import Process, Queue

wl_chars = set(open('wl.txt').read())
# wl_chars = set(open('../dic/wl.txt').read())
#NGワード
ng_words = set(word.strip() for word in open('../.ng_words').readlines())
ng_words2 = set(['日本酒','friends','時報','震度','toots','スク水','何の日','セカンダリー','お前','サイレンス','ブロック'])
ng_words = ng_words | ng_words2
aisatsu_words = set(['おや','おは','こん','おか','やっほ','てら','ただいま','おにい','その','時間','この','それ'])
pat1 = re.compile(r'《.*》|\||｜|［.*］|\[.*\]|^.\n')
pat3 = re.compile(r'^\n')
pat4 = re.compile(r'^.\n')
pat5 = re.compile(r'([。、…])\1+')
pat6 = re.compile(r'(.)\1{4,}')
WORKERS = 3
timeout = 5
BUF_LINES = 50000
EOF_SW = False
NRM_SW = []
un_func = unicodedata.normalize


def normalize(num,readQ,writeQ):
    print('--Process(%d) start' %(num) )
    while True:
        try:
            lines = readQ.get(timeout=timeout) #キューからトゥートを取り出すよー！
            outs = []
            for line in lines:
                try:
                    line = pat1.sub('',line)
                    for ng_word in ng_words:
                        # if ng_word in line:
                        if re.search(ng_word, line):
                            raise Exception
                    #挨拶が多い傾向なので、ｎ分の１にする
                    for word in aisatsu_words:
                        if word in line:
                            if random.randint(0,10) != 0:
                                raise Exception

                    # text = un_func("NFKC", line.strip()) + '\n'
                    text = line.strip() + '\n'
                    out = []
                    for c in list(text):
                        if c in wl_chars:
                            out.append(c)
                    outs.append( pat6.sub(r'\1',pat5.sub(r'\1',pat3.sub(r'',"".join(out) )) ))
                except:
                    continue
            writeQ.put(outs)
        except:
            return

def reader(readQ):
    lines = []
    print('--Start reading--')
    for i,line in enumerate(open(sys.argv[1], 'r')):
        lines.append(line)
        if i % BUF_LINES == BUF_LINES - 1:
            readQ.put(lines)
            lines = []
    print('--Finish reading--')

def writer(writeQ):
    with open(sys.argv[2],'w') as fo:
        while True:
            try:
                lines = writeQ.get(timeout=timeout)
                print('--Process(writer)::lines %d ' %(len(lines)) )
                fo.write("".join(lines))
            except:
                return
    print('--Finish writing--')

if __name__ == '__main__':
    readQ = Queue()
    writeQ = Queue()

    p_r = Process(target=reader, args=(readQ,))
    p_r.start()

    p_n = []
    for num in range(0,WORKERS-2):
        tmp  = Process(target=normalize, args=(num,readQ,writeQ))
        tmp.start()
        p_n.append(tmp)
    p_w = Process(target=writer, args=(writeQ,))
    p_w.start()

    p_r.join()
    for p_n_a in p_n :
        p_n_a.join()
    p_w.join()
