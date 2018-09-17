# -*- coding: UTF-8 -*-
'''
Created on 20171102
@author: leochechen
@Summary: 提供一些ctf的功能接口，供用例脚本调用。
'''
import os
from ctf_uitils import convert_str, convert_uni
from ctf_driver import CTFTestCase, CTFClientDriver, CTFRemoteDevice
from ctf_protocol import Command
from ctf_exps import *
# 异常回调类型
(CALLBACK, RERUN) = range(0, 2)
# 异常类型
(VARFAIL, VARABORT, VARNOTRUN, VARUNSUPPORTED, GROUPABORT, EXCEPTION) = \
    ('VarFail', 'VarAbort', 'GroupAbort', 'VarNotRun', 'VarUnsupported', 'Exception')


def alw(msg):
    '''
    在屏幕上打印字符串，调用这个函数时CTF Server也会记录打印的字符串。使用该接口时必须保证本地Client与CTF Server是连接的状态
    :param msg: 需打印的字符串
    :Usage:
        >>> alw("这个一个字符串")
        >>> 这是一个字符串
    :return:
    '''
    CTFClientDriver.send_command(Command.RECV_MESSAGE, msg)
    cmd, data = CTFClientDriver.recv_command()
    if cmd == Command.RECV_MESSAGE:
        print convert_str(data)
    else:
        raise CTFTestServerError("Client接口异常：Code{} Message:{}".format(cmd, convert_str(data)))


def get_var_record(key):
    '''
    获取当前用例中对于KEY的值。如存在这样的一个用例标签
	<var set="1" lvl="1" vid="1"  dsc="测试封装好的2D页" permutation="rows">
	    <rec key="package" dsc="app包名" >com.xxx.xxx.cb</rec>
	</var>
    :Usage:
        >>> get_var_record("package")
        >>> com.xxx.xxx.cb
    :param key: 对于记录的KEY
    :return:
    '''
    CTFClientDriver.send_command(Command.GET_VAR_RECORD, key)
    cmd, data = CTFClientDriver.recv_command()
    if cmd == Command.RECV_MESSAGE:
        return convert_str(data)
    else:
        raise CTFTestServerError("Client接口异常：Code{} Message:{}".format(cmd,data))


def get_testcase_info():
    '''
    获取当前用例的信息。使用该接口时必须保证本地Client与CTF Server是连接的状态
    :Usage:
        >>> get_testcase_info()
        >>>
    :return:
    '''
    CTFClientDriver.send_command(Command.GET_TESTCASE_INFO, "")
    cmd, data = CTFClientDriver.recv_command()
    if cmd == Command.RECV_MESSAGE:
        return data
    else:
        raise CTFTestServerError("Client接口异常：Code{} Message:{}".format(cmd,data))


def register_callback(exception, category, data):
    '''
    异常回调。向服务器注册异常回调的接口，如果有异常出现时服务器将会回调该接口。
    :param exception: 异常类型,目前支持VarFail、VarAbort、GroupAbort、VarNotRun、VarUnsupported、Exception
    :param category: 回调类型，目前支持 CALLBACK、RERUN
    :param data: 注册回调时需要的数据
    ：Usage:
        >>> # 注册异常回调
        >>> register_callback(EXCEPTION, CALLBACK, {"moudle": "common.Extend", "function":"Screenshot"})
        >>> # 注册异常重跑
        >>> register_callback(EXCEPTION, RERUN, {"count": 2})
    :return:
    '''
    CTFClientDriver.send_command(Command.REG_CALLBACK, (exception, category, data))
    cmd, data = CTFClientDriver.recv_command()
    if cmd == Command.RECV_MESSAGE:
        pass
    else:
        raise CTFTestServerError("Client接口异常：Code{} Message:{}".format(cmd, data))


def register_img_src(src):
    '''
    向服务器注册当前截图的文件路径
    :param src: 截图的文件路径
    :return:
    '''
    CTFClientDriver.send_command(Command.RECV_IMG_SRC, src)
    cmd, data = CTFClientDriver.recv_command()
    if cmd == Command.RECV_MESSAGE:
        pass
    else:
        raise CTFTestServerError("Client接口异常：Code{} Message:{}".format(cmd,data))


def ctf_shot(name="出现异常", suffix=".png"):
    '''
    在用例脚本中截图
    :param name: 截图名字
    :param suffix: 保存图片的后缀
    :return:
    '''
    info = get_testcase_info()
    # image_dir
    image_dir = info['env']['TESTCASE']['report']['image']
    if not os.path.isdir(image_dir):
        os.mkdir(image_dir)
    # case_dir
    case_dir = os.path.join(image_dir, u"{0}_{1}".format(convert_uni(info['html']), convert_uni(info['attrs']['vid'])))
    if not os.path.isdir(case_dir):
        os.mkdir(case_dir)
    filename = os.path.join(convert_uni(case_dir), convert_uni(name) + convert_uni(suffix))
    CTFRemoteDevice.screenshot(filename)
    # 向服务器注册当前截图的文件路径
    reg_filename = os.path.join('../image/', os.path.basename(case_dir), os.path.basename(filename))
    register_img_src(reg_filename)
    return filename


class ScreenshotWhenException(object):
    __metaclass__ = CTFTestCase
    '''
    向ctf server注册异常截图功能,支持以下几种功能的异常
    VarFail         当用例验证失败时触发
    VarAbort        当用例异常是触发
    GroupAbort      当grp标签中发生异常时触发
    VarNotRun       当用例没有运行时触发
    VarUnsupported  当用例发生不支持功能时触发
    Exception       当用例发生任何异常时触发
    '''
    def setup(self):
        register_callback(EXCEPTION, CALLBACK, {"moudle": self.__module__, "function": "ctf_shot"})

    def cleanup(self):
        pass


class ScreenshotWhenVarFail(object):
    __metaclass__ = CTFTestCase

    def setup(self):
        register_callback(VARFAIL, CALLBACK, {"moudle": self.__module__, "function": "ctf_shot"})

    def cleanup(self):
        pass


class ScreenshotWhenVarAbort(object):
    __metaclass__ = CTFTestCase

    def setup(self):
        register_callback(VARABORT, CALLBACK, {"moudle": self.__module__, "function": "ctf_shot"})

    def cleanup(self):
        pass


class ScreenshotWhenGroupAbort(object):
    __metaclass__ = CTFTestCase

    def setup(self):
        register_callback(GROUPABORT, CALLBACK, {"moudle": self.__module__, "function": "ctf_shot"})

    def cleanup(self):
        pass


class ScreenshotWhenVarNotRun(object):
    __metaclass__ = CTFTestCase

    def setup(self):
        register_callback(VARNOTRUN, CALLBACK, {"moudle": self.__module__, "function": "ctf_shot"})

    def cleanup(self):
        pass


class ScreenshotWhenVarUnsupported(object):
    __metaclass__ = CTFTestCase

    def setup(self):
        register_callback(VARUNSUPPORTED, CALLBACK, {"moudle": self.__module__, "function": "ctf_shot"})

    def cleanup(self):
        pass


class RerunWhenException(object):
    __metaclass__ = CTFTestCase

    def setup(self):
        register_callback(EXCEPTION, RERUN, {"count": int(get_var_record(key='count'))})

    def cleanup(self):
        pass


class RerunWhenVarAbort(object):
    __metaclass__ = CTFTestCase

    def setup(self):
        register_callback(VARABORT, RERUN, {"count": int(get_var_record(key='count'))})

    def cleanup(self):
        pass
