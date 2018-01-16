# -*- coding: utf-8 -*-

import os
import time
import subprocess

args = ['python', 'stream.py']

if __name__ == '__main__':
    while True:
        time.sleep(60)
        if not os.path.exists(".heartbeat"):
            time.sleep(60)
            if not os.path.exists(".heartbeat"):
                print('heart beat NG.\npython stream.py')
                subprocess.call(args)
            else:
                print('heart beat OK ',open('.heartbeat','r').read())
                os.remove(".heartbeat")
        else:
            print('heart beat OK ',open('.heartbeat','r').read())
            os.remove(".heartbeat")
