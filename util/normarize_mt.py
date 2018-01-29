# coding: utf-8

import sys
import io,re
import unicodedata
import threading, queue
import concurrent.futures
from time import sleep

wl_chars = set(open('../dic/wl2.txt').read())
#pat1 = re.compile(r'([^。])\n')
#pat2 = re.compile(r' +|　+')
pat3 = re.compile(r'^\n')
pat4 = re.compile(r'\n')
pat5 = re.compile(r'([。、…])\1+')
pat6 = re.compile(r'(.)\1{4,}')
WORKERS = 12
BUF_LINES = 10000
readQ = queue.Queue()
writeQ = [queue.Queue() for _ in range(0,WORKERS-2)]
EOF_SW = False
NRM_SW = []
un_func = unicodedata.normalize

def normalize(num):
    print('--Thread(%d) start' %(num) )
    while True:
        #print('Th(%d)readQ size = %d' %(num ,readQ.qsize()) ,readQ.empty(),EOF_SW )
        if  readQ.empty():
            sleep(1)
            if EOF_SW == True and readQ.empty():
                print( '--Thread:' + str(num) + ' finish--')
                NRM_SW.append(num)
                return '--Thread:' + str(num) + ' finish--'
            else:
                continue
        else:
            lines = readQ.get() #キューからトゥートを取り出すよー！
            #print('--Thread(%d)::lines %d ' %(num,len(lines)) )
            outs = []
            for line in lines:
                #text = unicodedata.normalize("NFKC", line.strip()) + '\n'
                text = un_func("NFKC", line.strip()) + '\n'
                out = []
                for c in list(text):
                    if c in wl_chars:
                        out.append(c)
                #outs.append( pat3.sub(r'',pat2.sub(r'。',pat1.sub(r'\1。\n',"".join(out) ))) )
                outs.append( pat6.sub(r'\1',pat5.sub(r'\1',pat3.sub(r'',"".join(out) )) ))

            writeQ[num].put(outs)

def reader():
    global EOF_SW
    lines = []
    print('--Start reading--')
    for i,line in enumerate(open(sys.argv[1], 'r')):
        lines.append(line)
        if i % BUF_LINES == BUF_LINES - 1:
            readQ.put(lines)
            #print('--Thread(reader)::lines %d ' %(len(lines)) )
            lines = []

    print('--Finish reading--')
    EOF_SW = True
    #print('--SW OFF--')
    return '--Finish reading--'

def writer():
    with open(sys.argv[2],'w') as fo:
        while len(NRM_SW) < WORKERS-2:
            for num in range(0,WORKERS-2):
                print('writeQ[%d] size = %d' %(num,writeQ[num].qsize()),writeQ[num].empty(), EOF_SW)
                print(NRM_SW)
                if  writeQ[num].empty():
                    pass
                else:
                    lines = writeQ[num].get()
                    print('--Thread(writer)::lines %d ' %(len(lines)) )
                    fo.write("".join(lines))
#                    for line in lines:
#                        fo.write(line)
    print('--Finish writing--')

if __name__ == '__main__':

    threading.Thread(target=reader).start()
    for num in range(0,WORKERS-2):
        print('thread:', num)
        threading.Thread(target=normalize, args=(num,)).start()
    threading.Thread(target=writer).start()

    #executor = concurrent.futures.ProcessPoolExecutor(max_workers=WORKERS)
    #executor = concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS)
    #futures = [executor.submit(reader), executor.submit(writer)]
    #futures.extend([executor.submit(normalize,num) for num in range(0,WORKERS-2)] )
    #for future in concurrent.futures.as_completed(futures):
    #    print(future.result())
    #executor.shutdown()
