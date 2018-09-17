# -*- coding=utf-8 -*-
'''
Created on 20180301 by leochechen
@summary: app启动时间用例逻辑
'''
from client import CTFTestCase, get_var_record, CTFJinja2Object, CTFUnitTestCase


class TestCase1(object):
    __metaclass__ = CTFTestCase

    def __init__(self):
        self.package = CTFJinja2Object.conf.ENV.TESTAPP.package.get_result()
        # 清理环境
        self._remote_device.app_clear_launch(self.package)
        # 小米5首次安装权限设置点击
        self._remote_device.watcher(name="confirm", interval=3).when(text='允许').click(text="允许")
        self._remote_device.watchers.run("confirm")

    def setup(self):
        '''
        app启动后点击跳出按钮，进入首页
        :return:
        '''
        skip_btn = CTFJinja2Object.app.native_ui_tree.skip_btn.get_result()
        self._remote_device.click_selector(skip_btn)
        # 有视频选卡出现
        video_tab = CTFJinja2Object.app.native_ui_tree.navigation_bar_bottom.video_tab.get_result()
        instance = self._remote_device.wait_exists_and_enabled(video_tab)
        CTFUnitTestCase.assertIsNotNone(instance)

    def cleanup(self):
        # 移除watcher
        self._remote_device.watchers.remove("confirm")
        # 关闭app
        self._remote_device.app_stop(self.package)
