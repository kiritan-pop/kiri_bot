# coding: utf-8

import sys,io,re,unicodedata,json

def main():
    cnt_dict = {}
    for line in open(sys.argv[1], 'r'):
        for c in list(line):
            if c in cnt_dict:
                cnt_dict[c] += 1
            else:
                cnt_dict[c] = 1

    sorted_dict = {}
    for k,v in sorted(cnt_dict.items(), key=lambda x: -x[1]):
        sorted_dict[k] = v

    with open('count_char.json','w') as fw:
        json.dump(sorted_dict,fw,indent=4,ensure_ascii=False)

    tmp = list(sorted_dict.keys())
    print(tmp)
    with open('wl.txt','w') as fw:
        fw.write("".join(tmp[0:2048]))

if __name__ == '__main__':
    main()
