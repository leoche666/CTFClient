# -*- coding: UTF-8 -*-
'''
Created on 20180730 by leochechen
@Summary: ctf远程设备封装(基于uiautomator2二次封装)
'''
import warnings
import time
import re
import os
import threading
from functools import wraps
from libs import six, yaml
from libs.uiautomator2 import UIAutomatorServer
from libs.uiautomator2 import adbutils
from libs.uiautomator import point, rect, param_to_property
from ctf_remote_engine import logger
from ctf_uitils import Singleton, convert_str
if six.PY2:
    import urlparse
    FileNotFoundError = OSError
else:  # for py3
    import urllib.parse as urlparse


def _is_wifi_addr(addr):
    if not addr:
        return False
    if re.match(r"^https?://", addr):
        return True
    m = re.search(r"(\d+\.\d+\.\d+\.\d+)", addr)
    if m and m.group(1) != "127.0.0.1":
        return True
    return False


def connect(addr=None):
    """
    Args:
        addr (str): uiautomator server address or serial number. default from env-var ANDROID_DEVICE_IP

    Returns:
        UIAutomatorServer

    Example:
        connect("10.0.0.1:7912")
        connect("10.0.0.1") # use default 7912 port
        connect("http://10.0.0.1")
        connect("http://10.0.0.1:7912")
        connect("cff1123ea")  # adb device serial number
    """
    if not addr or addr == '+':
        addr = os.getenv('ANDROID_DEVICE_IP')
    if _is_wifi_addr(addr):
        return connect_wifi(addr)
    return connect_usb(addr)


def connect_wifi(addr=None):
    """
    Args:
        addr (str) uiautomator server address.

    Returns:
        UIAutomatorServer

    Examples:
        connect_wifi("10.0.0.1")
    """
    if '://' not in addr:
        addr = 'http://' + addr
    if addr.startswith('http://'):
        u = urlparse.urlparse(addr)
        host = u.hostname
        port = u.port or 7912
        return CTFRemoteDevice(host, port)
    else:
        raise RuntimeError("address should start with http://")


def connect_usb(serial=None):
    """
    Args:
        serial (str): android device serial

    Returns:
        UIAutomatorServer
    """
    adb = adbutils.Adb(serial)
    lport = adb.forward_port(7912)
    d = connect_wifi('127.0.0.1:' + str(lport))
    if not d.agent_alive:
        warnings.warn("backend atx-agent is not alive, start again ...",
                      RuntimeWarning)
        adb.execute("shell", "/data/local/tmp/atx-agent", "-d")
        deadline = time.time() + 3
        while time.time() < deadline:
            if d.alive:
                break
    elif not d.alive:
        warnings.warn("backend uiautomator2 is not alive, start again ...",
                      RuntimeWarning)
        d.healthcheck()
    return d


class CTFJob(threading.Thread):
    def __init__(self, group=None, target=None, name=None,
                 args=(), kwargs={}, verbose=None, interval=1, times=-1):
        super(CTFJob, self).__init__(name=name)
        self.__name = name
        self.__target = target
        self.__args = args
        self.__kwargs = kwargs
        self.__interval = interval
        self.__times = times
        # 用于暂停线程的标识
        self.__flag = threading.Event()
        # 设置为True
        self.__flag.set()
        # 用于停止线程的标识
        self.__running = threading.Event()
        # 将running设置为True
        self.__running.set()

    def _control(self):
        if self.__target and self.__times > 0:
            self.__target(*self.__args, **self.__kwargs)
            self.__times -= 1
            if self.__times == 0:
                self.stop()
        elif self.__target and self.__times == -1:
            # print "invoke {}".format(self.name)
            self.__target(*self.__args, **self.__kwargs)
        else:
            raise EnvironmentError("target and times doesn't meet the conditions")

        time.sleep(self.__interval)

    def start(self):
        # 线程已经运行，则立即返回
        if self.isAlive():
            return
        else:
            super(CTFJob, self).start()

    def run(self):
        while self.__running.isSet():
            self.__flag.wait()
            self._control()

    def pause(self):
        self.__flag.clear()

    def resume(self):
        self.__flag.set()

    def stop(self):
        self.__flag.set()
        self.__running.clear()

    def __str__(self):
        return "<CTFJob-{} interval={} times={}>".format(self.__name, self.__interval, self.__times)

    def __repr__(self):
        return self.__str__()


class CTFRemoteDevice(UIAutomatorServer):
    __metaclass__ = Singleton

    def __init__(self, host, port=7912):
        self.ctfJobs = []
        super(CTFRemoteDevice, self).__init__(host, port)

    @property
    def host(self):
        return self._host

    @property
    def port(self):
        return self._port

    def __str__(self):
        return 'CTFRemoteDevice object for %s:%d' % (self._host, self._port)

    def __repr__(self):
        return str(self)

    def get_component_info(self):
        '''

        :return: 返回当前sdcard文件的最后一行，记录了当前对准控件的信息
        '''
        filename = "/sdcard/path.txt"
        interval = 1
        obj = self

        def _get_file_size():
            try:
                file_info = obj.adb_shell('ls -l {}'.format(filename))
                return int(re.split(r"\s+", file_info.strip())[-4])
            except Exception, ex:
                logger.error(str(ex))
                return 0

        _last_file_size = _get_file_size()
        while True:
            try:
                now_size = _get_file_size()
                if now_size != _last_file_size:
                    lines = obj.adb_shell('tail -n2 {}'.format(filename))
                    logger.info(lines)
                    _last_file_size = now_size
                time.sleep(interval)
            except Exception, ex:
                logger.error(str(ex))
                raise

    def app_install_local(self, apk):
        '''
        从本地路径安装apk文件
        :param apk: apk文件
        :return:
        '''
        # push to a folder
        filename = "/sdcard/{}.apk".format(int(time.time()))
        self.push(apk, filename)
        return self.adb_shell("pm install -r -t {}".format(filename))

    def app_exist(self, pkg_name):
        return True if pkg_name in self.adb_shell("pm list packages {}".format(pkg_name)) \
            else False

    def app_clear_launch(self, pkg_name):
        '''
        清楚app数据并拉起app
        :param pkg_name: app的包名
        :return:
        '''
        self.app_clear(pkg_name)
        self.app_start(pkg_name)

    def app_close_launch(self, pkg_name):
        '''
        强制杀死并拉起app
        :param pkg_name: app的包名
        :return:
        '''
        self.app_stop(pkg_name)
        self.app_start(pkg_name)

    def app_play_sound(self, sound):
        '''
        播放一段语音
        :param sound: 语音路径
        :return:
        '''
        remote_full_path = "/data/local/tmp/{}".format(int(time.time()))
        self.push(sound, remote_full_path)
        try:
            return self.jsonrpc.playSound(remote_full_path)
        finally:
            # delete remote file
            self.adb_shell("rm -rf {}".format(remote_full_path))

    def get_current_bightness(self):
        '''
        获取当前手机屏幕的亮度
        :return:
        '''
        return int(re.findall(r'\s*[a-zA-Z]+=(\d+)\s',
                              self.adb_shell("dumpsys power | grep -E mScreenBrightnessSetting=[0-9]+"), flags=0)[0])

    def get_current_max_bightness(self):
        '''
        获取当前手机屏幕的最大亮度
        :return:
        '''
        return int(re.findall(r'\s*[a-zA-Z]+=(\d+)\s',
                              self.adb_shell("dumpsys power | grep -E mScreenBrightnessSettingMaximum=[0-9]+"), flags=0)[0])

    def get_current_music_volume(self):
        '''
        获取当前手机的音量
        :return:
        '''
        return int(re.findall(r'.+\(speaker\)\S\s*(\d+).+',
                              self.adb_shell("dumpsys audio |grep STREAM_MUSIC -i -A 5"), flags=re.I | re.S)[0])

    def get_current_music_max_volume(self):
        '''
        获取当前手机的最大音量
        :return:
        '''
        return int(re.findall(r'.+Max\S\s*(\d+).+',
                              self.adb_shell("dumpsys audio |grep STREAM_MUSIC -i -A 5"), flags=re.I | re.S)[0])

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
                result = None
                try:
                    start_time = time.time()
                    while retry > 0:
                        # print "try to invoke {}".format(func)
                        result = func(*args, **kwargs)

                        if result:
                            break
                        else:
                            retry -= 1
                        time.sleep(interval)
                    else:
                        raise EnvironmentError(error)
                finally:
                    total_wait_time = time.time() - start_time
                    return result, total_wait_time
            return wrap_function
        return decorator

    def get_ctf_selector(self, instance=None, selector={}):
        assert type(selector) is dict
        extand, method = None, None
        if 'extand' in selector:
            extand = selector.pop('extand')
        if 'method' in selector:
            method = selector.pop('method')

        if instance is None:
            instance = self(**selector)
        else:
            instance = eval("tmp.{}".format(method), {"tmp": instance})(**selector)

        if extand is None:
            return instance
        else:
            return self.get_ctf_selector(instance=instance, selector=extand)

    def click_selector(self, selector, count=30, interval=1):
        '''
        点击一个navtive控件
        :param selector: ctf-ui-selector
        :param count: 循环次数
        :param interval: 一次的时间间隔
        :return:
        '''
        ui_selector = self.wait_exists_and_enabled(selector=selector, count=count, interval=interval)
        ui_selector.click()

    def wait_exists_and_enabled(self, selector, count=30, interval=1):
        '''
        判断native控件是否存在并且有效
        :param selector: ctf-ui-selector
        :param count: 循环次数
        :param interval: 一次的时间间隔
        :return:
        '''
        ui_selector = self.get_ctf_selector(instance=None, selector=selector)

        @self.wait_for_times(count=count, interval=interval, error="在{0}s内元素没有找到并生效".format(count*interval))
        def is_exists():
            return ui_selector.exists and ui_selector.info['enabled']
        is_exists()
        return ui_selector

    def ctf_selector_text(self, selector):
        '''
        获取ctf-ui-selector的文本内容
        :param selector: ctf-ui-selector
        :return:
        '''
        return convert_str(self.get_ctf_selector(instance=None, selector=selector).info['text'])

    def wait_exists(self, selector, timeout=5000):
        '''
        在一定时间内等待控件出现
        :param selector: ctf-ui-selector
        :param timeout: 超时时间
        :return:
        '''
        self.get_ctf_selector(instance=None, selector=selector).wait(timeout=timeout)

    def wait_gone(self, selector, timeout=5000):
        '''
        在一定时间内等待控件消失
        :param selector: ctf-ui-selector
        :param timeout: 超时时间
        :return:
        '''
        self.get_ctf_selector(instance=None, selector=selector).wait_gone(timeout=timeout)

    def get_centre(self, selector):
        '''
        获取ctf-ui-selector获取中心点的坐标
        :param selector: ctf-ui-selector
        :return:
        '''
        # Bounds (left,top) (right,bottom)
        bounds = self.get_ctf_selector(instance=None, selector=selector).info['visibleBounds']
        return point((bounds['right'] - bounds['left'])/2 + bounds['left'],
                     (bounds['bottom'] - bounds['top'])/2 + bounds['top'])

    def get_rect(self, selector):
        '''
        获取ctf-ui-selector的矩阵大小
        :param selector: ctf-ui-selector
        :return: {"top": top, "left": left, "bottom": bottom, "right": right}
        '''
        bounds = self.get_ctf_selector(instance=None, selector=selector).info['visibleBounds']
        return rect(**bounds)

    def swipe_to(self, _from, _to, steps=0.5):
        '''
        从ctf-ui-selector的_from目标滑动到_to目标,以steps为步长
        :param _from: ctf-ui-selector
        :param _to: ctf-ui-selector
        :param steps: 时长
        :return:
        '''
        my_to = self.get_centre(_to)
        my_from = self.get_centre(_from)
        self.swipe(my_from['x'], my_from['y'], my_to['x'], my_to['y'], steps)

    @property
    def swipe_until(self):
        '''
        :Usage:
            >>> # 从experience_device_first选择一个方向滑动到my_unknow_device存在为止
            >>> swipe_until.up(_from='_from', _to='_to')
            >>> swipe_until(orientation='up', _from='_from', _to='_to')
            >>> swipe_until.down( _from='_from', _to='_to')
            >>> swipe_until(orientation='down', _from='_from', _to='_to')
            >>> swipe_until.left(_from='_from', _to='_to')
            >>> swipe_until(orientation='left', _from='_from', _to='_to')
            >>> swipe_until.right(_from='_from', _to='_to')
            >>> swipe_until(orientation='right', _from='_from', _to='_to')
        :return:
        '''
        @param_to_property(orientation=['right', 'left', 'up', 'down'])
        def _swipe_until(orientation, _from, _to, steps=100, count=10, interval=0.1):
            '''
            从_from开始滑动直到 _to存在为止
            :param orientation: 滑动方向
            :param _from: ctf-ui-selector
            :param _to:  ctf-ui-selector
            :param steps： 滑动步长
            :param count: 滑动次数
            :param interval: 滑动间隔
            '''

            obj = self

            class SwipeHandler(object):
                def __init__(self, name):
                    self.start = obj.get_centre(name)

                @obj.wait_for_times(count=count, interval=interval,
                                    error="朝方向-{0}滑动{1}次后，没有发现{2}".format(orientation,count,_to))
                def until(self):
                    if orientation == 'up':
                        end = point(self.start['x'], self.start['y'] - steps)
                    elif orientation == 'down':
                        end = point(self.start['x'], self.start['y'] + steps)
                    elif orientation == 'left':
                        end = point(self.start['x'] - steps, self.start['y'])
                    elif orientation == 'right':
                        end = point(self.start['x'] + steps, self.start['y'])
                    else:
                        raise EnvironmentError("不支持的滚动方向-{}".format(orientation))
                    obj.swipe(self.start['x'], self.start['y'], end['x'], end['y'], steps=10)
                    return obj.get_ctf_selector(instance=None, selector=_to).exists
            SwipeHandler(_from).until()
        return _swipe_until

    def watcher(self, name, interval=1):
        obj = self

        class Watcher(object):
            def __init__(self):
                self.ctf_selectors = []

            @property
            def matched(self):
                @param_to_property(method=['click', 'press'])
                def _matched(method, args=(), kwargs={}):
                    for selector in self.ctf_selectors:
                        if not obj(**selector).exists:
                            return False
                    if method == 'click':
                        if obj(**kwargs).exists:
                            obj(**kwargs).click()
                    elif method == 'press':
                        for arg in args:
                            obj.press(arg)
                return _matched

            def when(self, **kwargs):
                self.ctf_selectors.append(kwargs)
                return self

            def click(self, **kwargs):
                obj.ctfJobs.append(CTFJob(name=name, target=lambda: self.matched.click(kwargs=kwargs), interval=interval))

            @property
            def press(self):
                @param_to_property(
                    "home", "back", "left", "right", "up", "down", "center",
                    "search", "enter", "delete", "del", "recent", "volume_up",
                    "menu", "volume_down", "volume_mute", "camera", "power")
                def _press(*args):
                    obj.ctfJobs.append(CTFJob(name=name, target=lambda: self.matched.press(args=args), interval=interval))
                return _press
        return Watcher()

    @property
    def watchers(self):
        obj = self

        class Watchers(list):
            def __init__(self):
                pass

            def find(self, name):
                for job in obj.ctfJobs:
                    if job.name == name:
                        return job
                raise EnvironmentError("没有找到task-{}".format(name))

            def pause(self, name):
                self.find(name).pause()

            def resume(self, name):
                self.find(name).resume()

            def run(self, name):
                return self.find(name).start()

            def remove(self, name):
                job = self.find(name)
                job.stop()
                obj.ctfJobs.remove(job)

            @property
            def all(self):
                return obj.ctfJobs
        return Watchers()
