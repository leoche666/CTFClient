# -*- coding=utf-8 -*-
'''
@modified: 20171025
@author: leochechen
@summary: Client和Server通信命令。传输数据类型为Json格式，以下为示例：
{
    CTFCMD: 协议命令,
    CTFDATA: {
    }
}
'''


class Command(object):
    (CTF_START,     # 单向命令server->client,框架启动
     CTF_CLOSE,     # 单向命令server->client,框架完成
     RECV_MESSAGE,  # 双向命令server<->client,接收信息
     RECV_FILE,     # 单向命令server->client,接收文件
     EXEC_MOUDLE,   # 单向命令server->clinet,执行模块
     EXEC_FNC,      # 单向命令server->client,执行函数
     EXEC_EXEC,     # 单向命令server->client,执行exec选项值
     GET_VAR_RECORD,     # 单向命令client->server,获取var记录值
     GET_TESTCASE_INFO,  # 单向命令client->server,获取用例信息
     REG_CALLBACK,       # 单向命令client->server,注册回调
     LOAD_HTML,        # 单向命令server->client,请求对应html文件
     LOAD_DIRECTORY,  # 单向命令server->client,请求对应文件夹中所有html文件
     SUCCESS,            # 双向命令server<->client,表示执行成功
     ERROR,              # 双向命令server<->client,表示执行失败
     RECV_IMG_SRC        # 单向命令client->server,注册截图路径
     ) = range(100, 115, 1)
