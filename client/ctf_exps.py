# -*- coding: UTF-8 -*-
'''
@author: leochechen
@summary: ctf framework运行过程中会出现的异常
'''


class FrameworkException(RuntimeError):
    '''
    框架异常
    '''
    pass


class CTFTestServerError(FrameworkException):
    '''
    CTF server出现异常
    '''
    pass


class CTFInvaildArg(FrameworkException):
    '''
    CTF传输数据异常
    '''
    pass


class CTFTestCaseCreateError(FrameworkException):
    '''
    CTF协议中不支持该种命令
    '''
    pass
