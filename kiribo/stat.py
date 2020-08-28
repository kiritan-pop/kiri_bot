# coding: utf-8

import psutil

def sys_stat():
        vm = psutil.virtual_memory()
        return {'cpu':psutil.cpu_percent(interval=1),'mem_total':vm.total, 'mem_available':vm.available, 'cpu_temp':psutil.sensors_temperatures()['coretemp'][0].current, 'disk_usage':psutil.disk_usage('/').free}

if __name__ == '__main__':
    from pprint import pprint as pp
    pp(sys_stat())
