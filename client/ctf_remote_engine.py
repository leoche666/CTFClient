# -*- coding: utf-8 -*-
import re
import time
import socket
import struct
import logging
import json
import threading
import xml.etree.ElementTree as ET
from collections import Iterable
from client.libs import socks
from functools import wraps
from abc import ABCMeta, abstractmethod
from wpyscripts.wetest.engine import GameEngine
from wpyscripts.common.wetest_exceptions import *
from ctf_uitils import Singleton, convert_str, convert_uni


def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s - %(filename)s:%(lineno)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger


logger = get_logger('ctf_unity_engine')
StrToBool = lambda rStr: True if rStr == "True" else False


class Socket5Client(object):

    def __init__(self, _host='localhost', _port=27018):
        self.host = _host
        self.port = _port
        self.socket = None
        # self.socket.connect((self.host, self.port))

    def _connect(self):
        self.socket = socks.socksocket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.socket.connect((self.host, self.port))

    def _send_data(self, data):
        try:
            serialized = json.dumps(data)
        except (TypeError, ValueError) as e:
            raise WeTestInvaildArg('You can only send JSON-serializable data')
        length = len(serialized)
        buff = struct.pack("i", length)
        self.socket.send(buff)
        self.socket.sendall(serialized)

    def _recv_data(self):
        length_buffer = self.socket.recv(4)
        if length_buffer:
            total = struct.unpack_from("i", length_buffer)[0]
        else:
            raise WeTestSDKError('recv length is None?')
        view = memoryview(bytearray(total))
        next_offset = 0
        while total - next_offset > 0:
            recv_size = self.socket.recv_into(view[next_offset:], total - next_offset)
            next_offset += recv_size
        # print str(view.tobytes())
        try:
            deserialized = json.loads(view.tobytes())
        except (TypeError, ValueError) as e:
            raise WeTestInvaildArg('Data received was not in JSON format')
        if deserialized['status'] != 0:
            message = "Error code: " + str(deserialized['status']) + " msg: "+deserialized['data']
            raise WeTestSDKError(message)
        return deserialized['data']

    def send_command(self, cmd, params=None, timeout=20):
        # if params != None and not isinstance(params, dict):
        #     raise Exception('Params should be dict')
        if not params:
            params = ""
        command = {
            "cmd": cmd,
            "value": params
        }
        for retry in range(0, 2):
            try:
                self.socket.settimeout(timeout)
                self._send_data(command)
                ret = self._recv_data()
                return ret
            except WeTestRuntimeError as e:
                raise e
            except socket.timeout:
                self.socket.close()
                self._connect()
                raise WeTestSDKError("Recv Data From SDK timeout")
            except socket.error as e:
                time.sleep(1)
                print("Retry...{0}".format(e.errno))
                self.socket.close()
                self._connect()
                continue
            except:
                time.sleep(1)
                print("Retry...")
                if self.socket:
                    self.socket.close()
                self._connect()
                continue
        raise Exception('Socket Error')


class UnityComponent(object):
    '''
    业务需求中不同控件有不同的行为属性。所以对于控件的操作区分对待。该类封装Unity控件的一些通用行为属性。可以继承该类根据业务封装一些控件
    '''

    # 等待控件消失或者隐藏的时间
    DISAPPEAR_OR_HIDE_INTREVAL = 10

    __metaclass__ = ABCMeta
    TAG = "component"

    @property
    def GameObject(self):
        return self.gameobject

    @property
    def Component(self):
        return type(self)

    @property
    def Index(self):
        return self.index

    @property
    def Element(self):
        return self.element if self.element \
            else self.get_element()

    @property
    def Elements(self):
        if self.total_elements:
            return self.total_elements
        else:
            self.get_element()
            return self.total_elements

    def __init__(self, engine, gameobject, index=None):
        self.engine = engine
        self.gameobject = gameobject
        self.index = index
        self.element = None
        self.total_elements = None
        self.total_wait_time = 0

    def wait_for_times(self, count, interval, error):
        '''
        每隔规定时间等待目前方法执行一次
        :param count: 重试的次数
        :param interval: 每一次重试的时间间隔
        :param error: 超时之后的错误提示
        :return: 一个目标函数的装饰器
        '''
        def decorator(func):
            @wraps(func)
            def wrap_function(*args, **kwargs):
                retry = count
                try:
                    start_time = time.time()
                    while retry > 0:
                        # print "try to invoke {}".format(func)
                        result = func(*args, **kwargs)

                        if result:
                            return result
                        else:
                            retry -= 1
                        time.sleep(interval)
                    else:
                        raise EnvironmentError(error)
                finally:
                    self.total_wait_time = time.time() - start_time

            return wrap_function
        return decorator

    def wait_interactive(self, properties=["enabled"], count=15, interval=2):
        '''
        在count*interval时间内等待控件可交互
        :param properties: 用于判断状态的属性值list
        :param count
        :param interval
        :return:
        '''
        obj = self

        @obj.wait_for_times(count=count, interval=interval, error="在{}秒内,没有检测到{}可交互".format(count*interval, obj))
        def wait_interactive_wrapper():
            return obj.is_interactive(properties)
        return wait_interactive_wrapper()

    def is_interactive(self, properties=["enabled"]):
        '''
        根据控件之上的一些属性值来判断该控件是否可以进行交互
        :param properties: 用于判断状态的属性值list
        :return:
        '''

        active_self = self.engine.get_gameobject_active(self.GameObject)
        rets = self.get_component_statuses(properties)
        return False if (not active_self) or len(filter(lambda status: status is False, rets)) > 0 else True

    def get_element(self, wait=True, count=30, interval=1):
        '''
        使用Gautomator的提供的查找函数，来查找一个符合的元素实例。找不到抛出异常
        1. self.index: 为None时，使用find_elment_wait来查找一个元素。
        2. self.index: 为其他的整数时，使用find_elements_path返回一个元素列表，取其中的对应索引的元素
        :param wait: 是否在count*interval时间内等待元素实例化
        :param count: 等待次数
        :param interval: 等待时间间隔
        :return: 找到的控件元素
        '''
        def get_element_once():
            if self.index is None:
                self.element = self.engine.find_element(self.gameobject)
                self.total_elements = [self.element]
            else:
                self.total_elements = self.engine.find_elements_path(self.gameobject)
                self.element = self.total_elements[self.index]

            return self.element

        return self.wait_for_times(count=count, interval=interval,
                                   error="在{}秒内,{}没有被实例化".format(count*interval, self))\
            (get_element_once)() if wait else get_element_once()

    def get_component_statuses(self, variables):
        '''
        获取自身一组属性的属性值
        :param element: element实例
        :param component:  组件名
        :param variables:  一组属性
        :return:  属性状态值
        '''
        assert hasattr(variables, '__iter__')
        return [StrToBool(convert_str(self.engine.get_component_field(self.Element, self.TAG, var))) for var in variables]

    def get_component_field(self, atr):
        '''
        获取控件上的属性值
        :param atr: 需要获取的属性值
        :return:
        '''
        return convert_str(self.engine.get_component_field(self.Element, self.TAG, atr))

    @abstractmethod
    def click(self):
        '''
        所有组件都需要有click行为
        :return:
        '''
        pass

    def wait_for_disappear_or_hide(self, properties=["enabled",], interval=0.1):
            '''
            等待控件消失或者隐藏。找不到该元素或者找到该元素但是隐藏了，满足其中一个条件则视为成功
            :param interval: 检测的时间间隔
            :return:
            '''
            obj = self
            count = int(self.engine.DISAPPEAR_OR_HIDE_INTREVAL / interval)

            @self.wait_for_times(count=count, interval=interval,
                                 error="在{}秒内没有隐藏或者消失".format(count*interval))
            def _get_disappear_or_hide_once():
                try:
                    # 找不到元素
                    # 找到元素但是元素的active属性是False
                    # 找到元素，元素的active属性是True，但是要求的属性列表中其中有个值是False
                    # 出现获取属性值发现异常
                    if obj.get_element(wait=False) \
                            and obj.engine.get_gameobject_active(obj.GameObject) \
                            and not (False in obj.get_component_statuses(properties)):
                        return False
                    else:
                        return True
                except Exception:
                    return True

            _get_disappear_or_hide_once()

    def __getattr__(self, item):
        '''
        定位Unity控件上的属性值的获取规则
        首先检查实例层或者类层是否含有该item，如果有则返回该属性值 -> 如果没有则从控件上去获取该属性值 -> 最后如果获取不到则抛出AttributeError
        :param item: 获取的属性值
        :return:
        '''
        # try:
        #     return super(UnityComponent, self).__getattribute__(item)
        # except:
        try:
            return self.get_component_field(item)
        except Exception, ex:
            raise AttributeError("{0}没有该{1}属性。Error:{2}".format(self, item, ex))

    def __str__(self):
        return "<Unity控件 Component={0} GameObject={1}>".format(self.TAG, self.GameObject) if self.Index is None\
            else "<Unity控件 Component={0} GameObject={1} Index={2}>".format(self.TAG, self.GameObject, self.Index)

    def __repr__(self):
        return self.__str__()


class RemoteGameEngine(GameEngine):
    __metaclass__ = Singleton

    def __init__(self, address, port):
        self.address = address
        self.port = port
        self.sdk_version = None
        self.socket = Socket5Client(self.address, self.port)


class CTFRemoteUnityEngine(RemoteGameEngine):
    __metaclass__ = Singleton

    __filed = {
        UnityComponent.TAG: UnityComponent,
    }

    def __init__(self, host, sock5_port=8719, sdk_port=27019):
        self._host = host
        self._sock5_port = sock5_port
        self._sdk_port = sdk_port
        # 使用sock5作为远程代理
        socks.set_default_proxy(socks.SOCKS5, self._host, self._sock5_port)
        # 使用格式化的文本获取指定Unity控件
        self.format1 = "^GameObject=(.+),Component=(\w+)$"
        self.format2 = "^GameObject=(.+),Component=(\w+),Index=(-?\d+)$"
        '''
        在3D分屏界面后台开启了视线晃动线程，主线程来做主要的控件操作。虽然python的线程同一时刻只会存在一个线程在真正的运行，但是两个线程都是使用共享的socket进行对手机的操作，线程的切换会混乱socket的发送和接收数据。
        所以要求主线程的控件操作和单次视线晃动操作都是原子操作，由python的threading库提供的Lock来实现加锁。 并且优化了Gautomator的SocketClinet收发函数，让socket的发送和接收数据的时候不可以被线程切换
        '''
        self.lock = threading.Lock()
        # axt-agent 将端口8719重定向到Gautomator SDK端口27019
        super(CTFRemoteUnityEngine, self).__init__("127.0.0.1", self._sdk_port)

    def __str__(self):
        return "CTFRemoteUnityEngine<host={},port={} -> host={},port={}> "\
            .format(self._host, self._sock5_port, "127.0.0.1", self._sdk_port)

    def __repr__(self):
        return self.__str__()

    def _lock_self(self, method, *args, **kwargs):
        try:
            # start = time.time()
            self.lock.acquire()
            return method(*args, **kwargs)
        finally:
            # print time.time() - start
            self.lock.release()

    def _parse_unity_format_str(self, frm_str):
        '''
        分割特定格式的字符串并返回元素结构体。
        :param frm_str: 分割字符串
        :return: gameobject,component 或者
                 gameobject,component,index的元组
        '''
        m1 = re.match(self.format1, convert_str(frm_str))
        m2 = re.match(self.format2, convert_str(frm_str))
        if m1:
            gameobject, component = m1.groups()
            instance =  self.__filed.get(component, UnityComponent)
            return instance(engine=self, gameobject=gameobject, index=None)
        elif m2:
            gameobject, component, index = m2.groups()
            instance =  self.__filed.get(component, UnityComponent)
            return instance(engine=self, gameobject=gameobject, index=int(index))
        else:
            raise EnvironmentError("请按照format={0} or {1}的格式传入定位字符串".format(self.format1, self.format2))

    def get_gameobjet(self, frm_str):
        '''
        从定位字符串中获取gameobject路径
        :param frm_str: 定位字符串
        :return: gameobject路径
        '''
        return self._parse_unity_format_str(frm_str).GameObject

    def get_component(self, frm_str):
        '''
        从定位字符串中获取控件名
        :param frm_str: 定位字符串
        :return: 控件名
        '''
        return self._parse_unity_format_str(frm_str).Component

    def get_index(self, frm_str):
        '''
        从定位字符串中索引
        :param frm_str: 定位字符串
        :return: 索引
        '''
        return self._parse_unity_format_str(frm_str).Index

    def get_element(self, frm_str):
        '''
        获取所定位的元素
        :param frm_str: 定位字符串
        :return: 元素实例
        '''
        return self._parse_unity_format_str(frm_str).Element

    def get_elements(self, frm_str):
        '''
        获取所定位的元素列表
        :param frm_str: 定位字符串
        :return: 所有符合条件的元素实例列表
        '''
        return self._parse_unity_format_str(frm_str).Elements

    def get_instance(self, frm_str):
        '''
        通过定位字符串获取控件实例
        :param frm_str:
        :return:
        '''
        return self._parse_unity_format_str(frm_str)

    def join_gameobject(self, gameobject, *keywords):
        '''
        拼接gameobject
        :param gameobject: 前缀gameobject
        :param keywords: 加入的gameobject的关键字
        :return: 拼接完的gameobject
        '''
        assert len(gameobject) > 0
        assert isinstance(keywords, Iterable)
        for keyword in keywords:
            gameobject += keyword if gameobject[-1] == '/' else '/' + keyword
        return gameobject

    def get_dump_tree(self, filename):
        '''
        获取Unity UI树
        :param filename: 保存UI树的文件名
        :return:
        '''
        source = self._get_dump_tree()
        tree = ET.ElementTree(ET.fromstring(source['xml']))
        # ui_file = os.path.join(os.path.dirname(__file__), filename)
        tree.write(filename, encoding='utf-8')

    def swipe(self, xyz, offset, direction='x', step=2, delay=2000):
        '''
        在delay时间内从xyz开始移动offset距离
        :param xyz: 世界坐标
        :param offset: 偏移
        :param direction: 方向，取值为['x','y','z']中的一个
        :param step:  步长
        :param delay:  执行时间
        :return:
        '''
        rotation = [float(i) for i in convert_str(xyz).split(',')]
        distance = float(offset) / step
        interval = float(delay) / step
        for i in range(step):
            if direction == 'x':
                rotation[1] += distance
            elif direction == 'y':
                rotation[0] += distance
            elif direction == 'z':
                rotation[2] += distance
            self.move('{0},{1},{2}'.format(*rotation))
            time.sleep(interval/1000)

    def wait_for_scene(self, name, max_count=20, sleeptime=2):
        '''
        等待场景获取成功
        :param name:
        :param max_count:
        :param sleeptime:
        :return:
        '''
        scene = None
        for i in range(max_count):
            try:
                scene = self.get_scene()
            except:
                time.sleep(sleeptime)

            if scene == name:
                return True
            time.sleep(sleeptime)
        return False
