#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys


class Singleton(type):
    # 单类构造的元类
    def __init__(cls, name, bases, attrs):
        super(Singleton, cls).__init__(name, bases, attrs)
        cls._instance = None

    def __call__(cls, *args, **kwargs):
        if cls._instance is None:
            # 以下不要使用'cls._instance = cls(*args, **kwargs)', 防止死循环,
            # cls的调用行为已经被当前'__call__'协议拦截了
            # 使用super(Singleton, cls).__call__来生成cls的实例
            cls._instance = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instance


def convert_str(x):
    '''
    返回编码为utf-8的string字符串
    :param x: 需要转换的unicode
    :return:
    '''
    if sys.version_info.major == 2:
        return x.encode('utf-8') if type(x) is unicode else x
    elif sys.version_info.major == 3:
        return x


def convert_uni(x):
    '''
    返回unicode的字符串
    :param x: 需要转换的string
    :return:
    '''
    if sys.version_info.major == 2:
        return x.decode("utf-8") if type(x) is str else x
    elif sys.version_info.major == 3:
        return x
