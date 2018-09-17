# -*- coding: UTF-8 -*-
'''
Created on 20180723 by leochechen
Summary 用于初始化CTF自动化测试框架 (基于uiautomator2)
'''
import os
import re
import time
import subprocess
import logging
import requests
import libs.uiautomator2.__main__ as uiautomator2_Installer
from libs.uiautomator2.__main__ import MyFire, log, appdir
from libs.uiautomator2.__main__ import Installer as Installer2
from libs import fire
from version import __ctf_apk_version__, __ctf_atx_agent_version__

CTF_APK_PACKAGE = "com.github.uiautomator"
CTF_TEST_APK_PACKAGE = "com.github.uiautomator.test"
CTF_APK_NAME = "app-uiautomator.apk"
CTF_TEST_APK_NAME = "app-uiautomator-test.apk"
CTF_ATX_AGENT_NAME = "ctf_atx_agent"


class Installer(Installer2):
    def __init__(self, serial=None):
        super(Installer, self).__init__(serial)

    def download_my_uiautomator_apk(self, apk_version):
        app_url = "https://github.com/leoche666/android-uiautomator-server/releases/" \
                  "download/%s/%s" % (apk_version, CTF_APK_NAME)
        app_test_url = "https://github.com/leoche666/android-uiautomator-server/releases/" \
                       "download/%s/%s" % (apk_version, CTF_TEST_APK_NAME)
        log.info("app-uiautomator.apk(%s) downloading ...", apk_version)
        path = uiautomator2_Installer.cache_download(app_url)

        log.info("app-uiautomator-test.apk(%s) downloading ...", apk_version)
        pathtest = uiautomator2_Installer.cache_download(app_test_url)
        return path, pathtest

    def install_ctf_apk(self, apk_version, reinstall=False):
        pkg_info = self.package_info(CTF_APK_PACKAGE)
        test_pkg_info = self.package_info(CTF_TEST_APK_PACKAGE)
        # For test_pkg_info has no versionName or versionCode
        # Just check if the com.github.uiautomator.test apk is installed
        if not reinstall and pkg_info and pkg_info['version_name'] == apk_version and test_pkg_info:
            log.info("apk(%s) already installed, skip", apk_version)
            return
        if pkg_info or test_pkg_info:
            log.debug("uninstall old apks")
            self.uninstall(CTF_APK_PACKAGE)
            self.uninstall(CTF_TEST_APK_PACKAGE)

        (path, pathtest) = self.download_my_uiautomator_apk(apk_version)
        self.install(path)
        log.info("%s installed" % CTF_APK_NAME)

        self.install(pathtest)
        log.info("%s installed" % CTF_TEST_APK_NAME)

    def install_ctf_atx_agent(self, agent_version, reinstall=False):
        version_output = self.shell(
            '/data/local/tmp/ctf_atx_agent', '-v', raise_error=False).strip()
        m = re.search(r"\d+\.\d+\.\d+", version_output)
        current_agent_version = m.group(0) if m else None
        if current_agent_version == agent_version:
            log.info("ctf_atx_agent(%s) already installed, skip", agent_version)
            return
        if current_agent_version == 'dev' and not reinstall:
            log.warn("ctf_atx_agent develop version, skip")
            return
        if current_agent_version:
            log.info("ctf_atx_agent(%s) need to update", current_agent_version)
        files = {
            'armeabi-v7a': 'ctf_atx_agent_v7a',
            'arm64-v8a': 'ctf_atx_agent_v8a',
            # 'armeabi': 'atx-agent_{v}_linux_armv6.tar.gz',
            # 'x86': 'atx-agent_{v}_linux_386.tar.gz',
        }
        log.info("ctf_atx_agent(%s) is installing, please be patient",
                 agent_version)
        abis = self.shell('getprop',
                          'ro.product.cpu.abilist').strip() or self.abi
        name = None
        for abi in abis.split(','):
            name = files.get(abi)
            if name:
                break
        if not name:
            raise Exception(
                "arch(%s) need to be supported yet, please message to 673965587@qq.com"
                % abis)

        app_url = "https://github.com/leoche666/atx-agent/releases/download/%s/%s" % (agent_version, name)
        path = uiautomator2_Installer.cache_download(app_url)
        log.debug("download ctf_atx_agent(%s) from github releases", agent_version)
        self.push(path, '/data/local/tmp/ctf_atx_agent', 0o755)
        log.debug("ctf_atx_agent installed")

    def check_apk_installed(self, apk_version):
        """ in OPPO device, if you check immediatelly, package_info will return None """
        pkg_info = self.package_info(CTF_APK_PACKAGE)
        if not pkg_info:
            raise EnvironmentError(
                "package %s not installed" % CTF_APK_PACKAGE)
        if pkg_info['version_name'] != apk_version:
            raise EnvironmentError(
                "package %s version expect \"%s\" got \"%s\""
                % (CTF_APK_PACKAGE, apk_version, pkg_info['version_name']))
        # test apk
        pkg_test_info = self.package_info(CTF_TEST_APK_PACKAGE)
        if not pkg_test_info:
            raise EnvironmentError(
                "package %s not installed" % CTF_TEST_APK_PACKAGE)

    def launch_and_check(self):
        log.info("launch ctf_atx_agent daemon")
        exedir = self.get_executable_dir()
        exefile = "%s/%s" % (exedir, 'ctf_atx_agent')
        args = ['TMPDIR=/sdcard', exefile, '-d']
        if self.server_addr:
            args.append('-t')
            args.append(self.server_addr)
        output = self.shell(*args)
        lport = self.forward_port(7912)
        log.debug("forward device(port:7912) -> %d", lport)
        time.sleep(.5)
        cnt = 0
        while cnt < 3:
            try:
                r = requests.get(
                    'http://localhost:%d/version' % lport, timeout=10)
                log.debug("ctf_atx_agent version: %s", r.text)
                # todo finish the retry logic
                log.info("ctf_atx_agent output: %s", output.strip())
                log.info("success")
                break
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.ReadTimeout):
                time.sleep(.5)
                cnt += 1
        else:
            log.error("failure")


class CtfFire(MyFire):
    def init(self,
             server=None,
             apk_version=__ctf_apk_version__,
             agent_version=__ctf_atx_agent_version__,
             verbose=False,
             reinstall=False,
             ignore_apk_check=False,
             proxy=None,
             serial=None,
             mirror=False):
        if verbose:
            log.setLevel(logging.DEBUG)
        if server:
            log.info("atx-server addr %s", server)
        if mirror:
            global GITHUB_BASEURL
            GITHUB_BASEURL = "http://openatx.appetizer.io"

        if proxy:
            os.environ['HTTP_PROXY'] = proxy
            os.environ['HTTPS_PROXY'] = proxy

        if not serial:
            output = subprocess.check_output(['adb', 'devices'])
            pattern = re.compile(
                r'(?P<serial>[^\s]+)\t(?P<status>device|offline)')
            matches = pattern.findall(output.decode())
            valid_serials = [m[0] for m in matches if m[1] == 'device']
            if len(valid_serials) == 0:
                log.warning("No avaliable android devices detected.")
                return
            log.info("Detect pluged devices: %s", valid_serials)
            for serial in valid_serials:
                self._init_with_serial(serial, server, apk_version,
                                       agent_version, reinstall,
                                       ignore_apk_check)
            # if len(valid_serials) > 1:
            #     log.warning(
            #         "More then 1 device detected, you must specify android serial"
            #     )
            #     return
            # serial = valid_serials[0]
        else:
            self._init_with_serial(serial, server, apk_version, agent_version,
                                   reinstall, ignore_apk_check)

    def _init_with_serial(self, serial, server, apk_version, agent_version,
                          reinstall, ignore_apk_check):
        log.info("Device(%s) initialing ...", serial)
        ins = Installer(serial)
        ins.server_addr = server
        ins.install_minicap()
        ins.install_minitouch()
        ins.install_ctf_apk(apk_version, reinstall)
        ins.install_ctf_atx_agent(agent_version, reinstall)
        if not ignore_apk_check:
            ins.check_apk_installed(apk_version)
        ins.launch_and_check()

    def cleanup(self):
        raise NotImplementedError()


def main():
    fire.Fire(CtfFire)


if __name__ == '__main__':
    main()
