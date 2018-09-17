# -*- coding: UTF-8 -*-
'''
@created on 20171026
@modified on 20180802
@author: leochechen
@Summary: ctf根据从Server端接收到的数据驱动运行
'''
import re
import os
import sys
import inspect
import time
import pickle
import json
import socket
import struct
import threading
import importlib
import traceback
from ctf_protocol import Command
from ctf_exps import *
from ctf_remote_device import CTFRemoteDevice, CTFJob
from ctf_remote_engine import CTFRemoteUnityEngine
from ctf_uitils import Singleton
from libs import yaml
from libs.unittest import TestCase
from libs.jinja2 import Environment
from libs.jinja2 import FileSystemLoader
from ctf_uitils import convert_uni, convert_str


class CTFClassAsInstance(object):
    def __init__(self, cls):
        self.__cls__ = cls
        self.__instance__ = None

    def __call__(self, *args, **kwargs):
        if self.__instance__ is None:
            self.__instance__ = self.__cls__(*args, **kwargs)
            return self
        else:
            return self.__instance__(*args, **kwargs)

    def __str__(self):
        return "{} <instance object {}>".format(type(self).__name__, self.__instance__) if self.__instance__ \
            else "{} <class object {}>".format(type(self).__name__, self.__cls__.__name__)

    def __repr__(self):
        return self.__str__()

    def __getattr__(self, item):
        # 当所修饰的类没有实例化之前从类中获取属性，实例化之后从实例中获取属性
        if self.__instance__ is None:
            return getattr(self.__cls__, item)
        else:
            return getattr(self.__instance__, item)


class CTFSocketClient(object):
    __metaclass__ = Singleton
    # (HOST, PORT) = '10.110.87.14', 6777
    (HOST, PORT) = 'localhost', 6777

    def __init__(self):
        self.timeout = 30
        self.host = self.HOST
        self.port = self.PORT
        self.lock = threading.Lock()
        self.socket = socket.SocketType(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._connect()

    def __str__(self):
        return "<sockect host:{} port:{}>".format(self.host, self.port)

    def __repr__(self):
        return self.__str__()

    def _connect(self):
        # 尝试3次与ctf Server建立连接
        retry = 3
        while True:
            try:
                print "正在请求连接CTF Server({},{})...".format(self.host,self.port)
                self.socket.connect((self.host, self.port))
                return
            except Exception, e:
                retry -= 1
                if retry == 0:
                    print "连接失败..."
                    raise
                else:
                    continue

    def send_data(self, data):
        try:
            serialized = json.dumps(data)
        except (TypeError, ValueError) as e:
            raise CTFInvaildArg('你只能发送能够被JSON序列化的数据')
        # 尝试两次发送
        for retry in range(0, 2):
            try:
                self.lock.acquire()
                length = len(serialized)
                buff = struct.pack("i", length)
                self.socket.send(buff)
                self.socket.sendall(serialized)
                break
            except socket.timeout:
                self.socket.close()
                self._connect()
                raise CTFTestServerError("从CTF服务器接收数据超时")
            except socket.error as e:
                time.sleep(1)
                print("Retry...{0}".format(e.errno))
                self.socket.close()
                self._connect()
                continue
            finally:
                self.lock.release()

    def recv_data(self):
        try:
            self.lock.acquire()
            length_buffer = self.socket.recv(4)
            if length_buffer:
                total = struct.unpack_from("i", length_buffer)[0]
            else:
                raise CTFTestServerError('recv length is None?')

            view = memoryview(bytearray(total))
            next_offset = 0
            while total - next_offset > 0:
                recv_size = self.socket.recv_into(view[next_offset:], total - next_offset)
                next_offset += recv_size
        finally:
            self.lock.release()

        try:
            deserialized = json.loads(view.tobytes())
            return deserialized
        except (TypeError, ValueError) as e:
            raise CTFInvaildArg('Data received was not in JSON format')

    def close(self):
        self.socket.close()


@CTFClassAsInstance
class CTFUnitTestCase(TestCase):
    __metaclass__ = Singleton

    # 一个Unit testcase的模板类
    '''
    常用assert的断言方法
    assertEqual(a,b，[msg='测试失败时打印的信息'])：若 a=b，则测试用例通过
    assertNotEqual(a,b，[msg='测试失败时打印的信息'])：若a != b，则测试用例通过
    assertTrue(x，[msg='测试失败时打印的信息'])：若x是True，则测试用例通过
    assertFalse(x，[msg='测试失败时打印的信息'])：若x是False，则测试用例通过
    assertIs(a,b，[msg='测试失败时打印的信息'])：若a是b，则测试用例通过
    assertNotIs(a,b，[msg='测试失败时打印的信息'])：若a不是b，则测试用例通过
    assertIsNone(x，[msg='测试失败时打印的信息'])：若x是None，则测试用例通过
    assertIsNotNone(x，[msg='测试失败时打印的信息'])：若x不是None，则测试用例通过
    assertIn(a,b，[msg='测试失败时打印的信息'])：若a在b中，则测试用例通过
    assertNotIn(a,b，[msg='测试失败时打印的信息'])：若a不在b中，则测试用例通过
    assertIsInstance(a,b，[msg='测试失败时打印的信息'])：若a是b的一个实例，则测试用例通过
    assertNotIsInstance(a,b，[msg='测试失败时打印的信息'])：若a不是b的实例，则测试用例通过
    assertAlmostEqual(a, b)：round(a-b, 7) == 0
    assertNotAlmostEqual(a, b)：round(a-b, 7) != 0
    assertGreater(a, b)：a > b     
    assertGreaterEqual(a, b)：a >= b     
    assertLess(a, b)：a < b     
    assertLessEqual(a, b)：a <= b     
    assertRegexpMatches(s, re)：regex.search(s)     
    assertNotRegexpMatches(s, re)：not regex.search(s)     
    assertItemsEqual(a, b)：sorted(a) == sorted(b) and works with unhashable objs     
    assertDictContainsSubset(a, b)：all the key/value pairs in a exist in b     
    assertMultiLineEqual(a, b)：strings     
    assertSequenceEqual(a, b)：sequences     
    assertListEqual(a, b)：lists     
    assertTupleEqual(a, b)：tuples     
    assertSetEqual(a, b)：sets or frozensets     
    assertDictEqual(a, b)：dicts
    '''

    def __init__(self):
        super(type(self), self).__init__(methodName='testmy')

    def testmy(self):
        pass


class CTFClientMoudle(object):
    # 为当前模块增加内置实例的方法
    '''
    1. my_self:  返回导入模块的实例
    2. unittest: 返回unittest.TestCase实例
    3. device: 返回当前连接的CTFRemoteDevice实例
    4. engine: 返回当前unity引擎实例（需代码里自己测试该引擎是否连接成功）
    '''
    def __init__(self, name):
        self._name = name
        self._my_self = importlib.import_module(name)
        self._map_loading = {
            "my_self": self._my_self,
            "unittest": CTFUnitTestCase,
            "device": CTFRemoteDevice,
            "engine": CTFRemoteUnityEngine
        }
        self._last_instance = None

    @property
    def name(self):
        return self._name

    @property
    def my_self(self):
        return self._my_self

    @property
    def unittest(self):
        return CTFUnitTestCase

    @property
    def device(self):
        return CTFRemoteDevice

    @property
    def engine(self):
        return CTFRemoteUnityEngine

    def add_instance(self, instance):
        '''
        获取实例中所有的公有方法
        :param instance: 获取共有方法的实例
        :return:
        '''
        method_list =  [(method, getattr(instance, method)) for method in dir(instance)
                        if callable(getattr(instance, method)) and not method.startswith('__') and not method.startswith('_')]

        for name, method in method_list:
            self.add_method(name, method)

    def _try_getattr(self, name, item):
        try:
            return getattr(self._map_loading[name], item)
        except AttributeError:
            return False

    def __str__(self):
        return "{} <{} map-key self unittest device engine>".format(type(self).__name__, self.name)

    def __repr__(self):
        return self.__str__()

    def __getattr__(self, item):
        # 默认属性获取：    clientModule.my_self.click
        # 指定获取属性方式： clientModule.my_self.click  clientModule.unittest.assertEqual
        # clientModule.device.click  clientModule.engine.get_sdk_version
        try:
            if self._last_instance:
                raise AttributeError()
            return getattr(self._map_loading['my_self'], item)
        except AttributeError:
            m = re.search(r'(?P<instance>{})'.format('|'.join(self._map_loading.keys())), item, re.S | re.U)
            if m and self._last_instance is None:
                self._last_instance = self._map_loading[m.group('instance')]
                return self
            elif self._last_instance:
                try:
                    return getattr(self._last_instance, item)
                finally:
                    self._last_instance = None
            else:
                return getattr(self._map_loading['my_self'], item)


class CTFTestCase(type):
    '''
    class TestCase(object):
        __metaclass__ = CTFTestCase

        def __init__(self):
            pass

        def setup(self):
            pass

        def cleanup(self):
            pass
    '''
    def __init__(cls, name, bases, attrs):
        super(CTFTestCase, cls).__init__(name, bases, attrs)
        cls._custom_module = CTFClientMoudle
        cls._remote_device = CTFRemoteDevice
        cls._remote_engine = CTFRemoteUnityEngine

    def __call__(cls, *args, **kwargs):
        # cls的调用行为已经被当前'__call__'协议拦截了, 依次调用cls实例 setup()和cleanup()方法
        # 使用super(CTFTestCase, cls).__call__来生成cls的实例
        if '__custom_module__' in kwargs:
            # CTFClientDriver驱动CTFTestCase实例时会传入custom_module
            cls._custom_module = kwargs.pop('__custom_module__')
        instance = super(CTFTestCase, cls).__call__(*args, **kwargs)

        if not hasattr(instance, 'setup'):
            raise CTFTestCaseCreateError("{} testcase instance must have setup method..."
                                         .format(cls.__module__ + '.' + cls.__name__))

        if not hasattr(instance, 'cleanup'):
            raise CTFTestCaseCreateError("{} testcase instance must have cleanup method..."
                                         .format(cls.__module__ + '.' + cls.__name__))

        try:
            instance.setup()
        finally:
            instance.cleanup()
        return instance


@CTFClassAsInstance
class CTFJinja2Object(object):
    def __init__(self):
        self._parms = {}
        self._jinja2_env = Environment()
        self._jinja2_env.filters['ctf_ui'] = self.ctf_ui
        self._jinja2_env.filters['get_params'] = self.get_params

    def get_jinja_env(self):
        return self._jinja2_env

    def set_loader(self, searchpath=[]):
        self._jinja2_env.loader = FileSystemLoader(searchpath=searchpath)

    def load_yaml(self, map_key, path):
        '''
        使用一个map_key对yaml文件进行映射获取
        :param map_key: map_key
        :param path: yaml文件路劲
        :return:
        '''

        if map_key not in self._parms:
            self._parms[map_key] =  yaml.load(stream=open(path, 'rb').read())

    def get_params(self, name, locations):
        return eval("tmp.{}.{}.get_result()".format(name, locations), {"tmp": self})

    def ctf_ui(self, name, locations):
        ret =  self.get_params(name, locations)
        assert "GameObject" in ret and "Component" in ret
        return "GameObject={},Component={}".format(ret['GameObject'], ret['Component'])

    def __str__(self):
        return "{} <id={}>".format(type(self).__name__, id(self))

    def __repr__(self):
        return self.__str__()

    def __getattr__(self, item):
        for i in range(2):
            if item in self._parms:
                class CTFParamObject(object):
                    def __init__(self, _yaml):
                        self._yaml = _yaml

                    def get_result(self):
                        return self._yaml

                    def __getattr__(self, iitem):
                        if iitem in self._yaml:
                            return CTFParamObject(self._yaml[iitem])
                        else:
                            raise AttributeError("{} error!!!".format(iitem))
                return CTFParamObject(self._parms[item])
            else:
                try:
                    filename = os.path.join(self.conf.ENV.TESTCASE.params.get_result(), '.'.join([item, "yaml"]))
                    self.load_yaml(map_key=item, path=filename)
                    continue
                except:
                    raise AttributeError("{} error!!!".format(item))


@CTFClassAsInstance
class CTFClientDriver(object):
    def __init__(self):
        self._sock_client = CTFSocketClient()
        self._moudles = {}

    def __str__(self):
        return "CTFClientDriver server:{} device:{}".format(self._sock_client, self._remote_device)

    def __repr__(self):
        return self.__str__()

    def _try_exption(self):
        pass

    @property
    def current_moudle(self):
        # class被ClassAsInstance装饰器修饰调用时，堆栈需要回退两层才能到达指定调用函数的frame对象
        invoke_frame = inspect.currentframe().f_back.f_back
        module_name = inspect.getmodule(invoke_frame).__name__
        return self.get_current_moudle(module_name)

    def get_current_moudle(self, module_name):
        if module_name in self._moudles:
            return self._moudles.get(module_name, None)
        else:
            raise EnvironmentError("{} doesn't have module name: {}".format(self, module_name))

    @classmethod
    def ctf_start(cls, path):
        '''
        ctf框架启动
        :param path: 启动需要的配置文件路径
        :return:
        '''
        CTFJinja2Object()
        CTFJinja2Object.load_yaml(map_key="conf", path=path)
        template = CTFJinja2Object.conf.ENV.TESTCASE.template.get_result()
        workspace = CTFJinja2Object.conf.ENV.TESTCASE.workspace.get_result()
        CTFJinja2Object.set_loader(searchpath=[template, workspace])
        for host in CTFJinja2Object.conf.DEVICE.HOST.get_result():
            # TODO 支持多设备并发运行
            CTFRemoteDevice(host=host)
            CTFRemoteUnityEngine(host=host)
            CTFClientDriver()

            # print CTFRemoteDevice.serial
            # 启动ctf测试框架
            CTFClientDriver.start(data={
                    'cmd': pickle.dumps(sys.argv),
                    'serial': CTFRemoteDevice.serial,
                    'env': CTFJinja2Object.conf.ENV.get_result(),
            })

    def send_command(self, cmd, params):
        '''
        向服务器发送命令
        :param cmd: 命令
        :param params: 数据
        :return:
        '''
        self._sock_client.send_data({
            'CTFCMD': cmd,
            'CTFDATA': params
        })

    def recv_command(self):
        '''
        接收一条服务器命令，返回命令、数据
        :return:
        '''
        ret = self._sock_client.recv_data()
        return ret['CTFCMD'], ret['CTFDATA']

    def start(self, data):
        '''
        向服务器发送一条启动命令，并进入事件循环池，等待接收服务器的控制
        :param data:
        :return:
        '''
        self.send_command(Command.CTF_START, data)
        self.event_loop()

    def load_moudle(self, name):
        '''
        加载本地指定模块
        :param name: 模块路径
        :return:
        '''
        name = convert_str(name)
        if name not in self._moudles:
            self._moudles[name] = CTFClientMoudle(name)
        self.send_command(Command.SUCCESS, name)

    def load_fnc(self, data):
        '''
        从本地指定模块中加载指定函数运行
        :param data: 从服务器端发送过来需要解析的数据
        :return:
        '''
        m, f, a = convert_str(data['moudle']), convert_str(data['fnc']), map(convert_str, data['args'])
        if m not in self._moudles:
            self._moudles[m] = CTFClientMoudle(m)
        method = eval("tmp.{}".format(f), {"tmp": self._moudles[m]})
        ret = method(*a)
        # for item in f.split('.'):
        #     instance = getattr(instance, item)
        # else:
        #     ret = instance(*a)
        self.send_command(Command.SUCCESS, ret)

    def load_exec(self, data):
        '''
        加载Cluster自定义解释逻辑
        :param data: 从服务器端发送过来需要解析的数据
        :return:
        '''
        m, e = convert_str(data['moudle']), convert_str(data['exec'])
        fnc = getattr(self._moudles[m], e)
        fnc(__custom_module__=self._moudles[m])
        self.send_command(Command.SUCCESS, "")

    def load_html(self, data):
        '''
        加载指定的xml文件
        :param data: 从服务器端发送过来需要解析的数据
        :return:
        '''
        tmpl = CTFJinja2Object.get_jinja_env().get_template(data['html'])
        html = tmpl.render(data['kwargs'])
        self.send_command(Command.SUCCESS, {'html': html})

    def load_directory(self, data):
        '''
        加载指定目录下的xml文件
        :param data: 从服务器端发送过来需要解析的数据
        :return:
        '''
        xmls = []
        for root, dirs, files in os.walk(data['directory']):
            for f in files:
                filename, suffix = os.path.splitext(f)
                if suffix == '.xml':
                    xmls.append(filename)
        self.send_command(Command.SUCCESS, {'xmls': xmls})

    def load_file(self, data):
        '''
        数据写入文件
        :param data: 从服务器端发送过来需要解析的数据
        :return:
        '''
        directory, filename, content = data['directory'], data['filename'], convert_str(data['content'])
        if not os.path.isdir(directory):
            os.mkdir(directory)
        _file = file(os.path.join(directory, filename), 'w')
        _file.write(content)
        _file.close()

    def event_loop(self):
        '''
        Client事件循环池，根据从Server接收到命令来驱动事件运行
        :return:
        '''
        while True:
            cmd, data = self.recv_command()
            try:
                if cmd == Command.RECV_MESSAGE:
                    print convert_str(data)
                elif cmd == Command.RECV_FILE:
                    self.load_file(data)
                elif cmd == Command.EXEC_MOUDLE:
                    self.load_moudle(data)
                elif cmd == Command.EXEC_FNC:
                    self.load_fnc(data)
                elif cmd == Command.EXEC_EXEC:
                    self.load_exec(data)
                elif cmd == Command.LOAD_HTML:
                    self.load_html(data)
                elif cmd == Command.LOAD_DIRECTORY:
                    self.load_directory(data)
                elif cmd == Command.CTF_CLOSE:
                    break
            except Exception:
                self.send_command(Command.ERROR, traceback.format_exc())


CTFUnitTestCase()
CTFRemoteDevice = CTFClassAsInstance(CTFRemoteDevice)
CTFRemoteUnityEngine = CTFClassAsInstance(CTFRemoteUnityEngine)
