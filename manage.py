# -*- coding: utf-8 -*-
'''
@created on: 20170711
@modified on: 20180801
@author: leochechen
@summary: CTF启用脚本，用来解析ctf命令行参数
@ctf command: python manage.py -xml(选择用例数据配置文件) 运行方式 -serial 指定需运行的设备
'''
from client import CTFClientDriver

if __name__ == '__main__':
    CTFClientDriver.ctf_start(path="configuration.yaml")
