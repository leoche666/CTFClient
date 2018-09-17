# -*- coding=utf-8 -*-
import re
import os
import time
import math
import json
import zipfile
import urllib2
from client import CTFTestCase, CTFClientDriver, CTFJinja2Object
from client import get_var_record, alw, convert_str
from client import ctf_shot


class InitApp(object):
    __metaclass__ = CTFTestCase

    # 清理app数据
    def __init__(self):
        self.testapp = CTFJinja2Object.conf.ENV.TESTAPP.get_result()

    def get_apk(self):
        version, expansion, build = self.testapp['version'], self.testapp['expansion'], self.testapp['build']
        # 当版本和拓展为空时，从默认接口中直接获取
        if version or expansion:
            max_version, max_ex_version = self.int_to_version(version), self.int_to_version(expansion)
        else:
            max_version, max_ex_version = self.get_max_version_id()

        zip_url_template = self.testapp['template_url']
        zip_dir = "common/tmp"
        if not os.path.isdir(zip_dir):
            os.makedirs(zip_dir)
        zip_filename = os.path.join(zip_dir, os.path.basename(zip_url_template))

        # download zip
        download_url = zip_url_template.format(max_version, max_ex_version, build)
        alw("download zip from: {0},please wait...".format(download_url))
        f = urllib2.urlopen(download_url)
        data = f.read()
        with open(zip_filename, "wb") as code:
            code.write(data)

        # unzip zip
        apk_ex_dir = self.unzip(zip_filename)
        # return apk path
        return self.get_file_by_suffix(apk_ex_dir)[0]

    def get_max_version_id(self, pattern="ivr(\d)\.(\d)\.(\d)_google_build"):
        '''
        从api接口里取出最大的版本号
        :return:
        '''
        f = urllib2.urlopen(self.api_url)
        data = json.loads(f.read())
        versions = []
        for item in data['jobs']:
            match = re.match(pattern, item['name'])
            if match:
                version_id = self.version_to_int(match.groups(1))
                versions.append(version_id)
        max_ex_version = max(list(set(versions)))
        max_version = max_ex_version / 10
        return self.int_to_version(max_version), self.int_to_version(max_ex_version)

    def check_app_version(self, package, version):
        stdout = self._remote_device.adb_shell("dumpsys package {}".format(package))
        ret = re.search("versionName=CB.(\d)+\.(\d+)\.(\d+)", stdout)
        _ret_version = ''.join(map(lambda t: str(int(t)), ret.groups()))
        return int(_ret_version) == version

    def setup(self):
        if not self._remote_device.app_exist(self.testapp['package']) \
                or not self.check_app_version(self.testapp['package'], self.testapp['expansion']):
            apk_full_path = self.get_apk()
            alw("install apk from: {0},please wait...".format(apk_full_path))
            stdout = self._remote_device.app_install_local(apk_full_path)
            if 'Success' not in stdout:
                raise EnvironmentError("安装apk失败,请检查环境!\nerror:{0}".format(stdout))
        self._remote_device.app_clear(self.testapp['package'])

    def cleanup(self):
        pass

