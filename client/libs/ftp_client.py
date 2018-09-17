# coding: utf-8
import os
import ftplib
import socket


# 上传指定文件到 ftp 服务器
def uploadFile(dir_ftp, filename_ftp, filepath_local, host, port, username, password):
    """
    参数说明：
    * dir_ftp: 在 ftp 服务器上存储文件的路径；
    * filename_ftp: 存储到 ftp 服务器上的文件名；
    * filepath_local: 需要上传的本地源文件路径；
    * host: ftp 服务器地址（ip/域名）；
    * port: ftp 服务器端口号，一般是 21；
    * username、password: 登陆 ftp 服务器时的用户名和密码。
    """
    if not os.path.exists(filepath_local):
        print '找不到指定的源文件，请检查路径配置。'
        return False
    # connect
    try:
        f = ftplib.FTP()
        f.connect(host=host, port=port)
    except (socket.error, socket.gaierror), e:
        print '----ERROR:cannot reach ' + host
        print e
        return False
    # login
    try:
        f.login(user=username, passwd=password)
    except ftplib.error_perm, e:
        print '----ERROR:cannot login to server ' + host
        print e
        f.quit()
        return False
    print '****Logged in as ' + username + ' to server ' +host
    # change folder
    try:
        f.cwd(dir_ftp)
    except ftplib.error_perm, e:
        print '----ERROR:cannot CD to %s on %s' % (dir_ftp, host)
        print e
        f.quit()
        return False
    print '**** changed to %s folder on %s' % (dir_ftp, host)
    # upload file
    try:
        f.storbinary('STOR ' + filename_ftp, open(filepath_local, 'rb'))
    except ftplib.error_perm, e:
        print '----ERROR:cannot write %s on %s' % (filename_ftp, host)
        print e
        return False
    else:
        print '****Uploaded ' + filepath_local + ' to ' + host + ' as '\
            + os.path.join(dir_ftp, filename_ftp)
        f.quit()
        return True


# 登陆 ftp 服务器下载文件（保存到当前目录）
def getServerFile(dir_ftp, filename, host, port, username, password):
    """
    参数说明：
    * dir_ftp: 目标文件在 ftp 服务器上路径；
    * filename: 目标文件名；
    * host: ftp 服务器地址（ip/域名）；
    * port: ftp 服务器端口号，一般是 21；
    * username、password: 登陆 ftp 服务器时的用户名和密码。
    """
    if os.path.exists(filename):
        print '****the file ' + filename + ' has already exist! The file will be over writed'
    # connect
    try:
        f = ftplib.FTP()
        f.connect(host=host, port=port)
    except (socket.error, socket.gaierror), e:
        print '----ERROR:cannot reach ' + host
        print e
        return False
    # login
    try:
        f.login(user=username, passwd=password)
    except ftplib.error_perm, e:
        print '----ERROR:cannot login to server ' + host
        print e
        f.quit()
        return False
    print '****Logged in as ' + username + ' to server ' +host
    # change folder
    try:
        f.cwd(dir_ftp)
    except ftplib.error_perm, e:
        print '----ERROR:cannot CD to %s on %s' % (dir_ftp, host)
        print e
        f.quit()
        return False
    print '**** changed to %s folder on %s' % (dir_ftp, host)
    # get file
    try:
        f.retrbinary('RETR %s' % filename, open(filename, 'wb').write)
    except ftplib.error_perm, e:
        print '----ERROR:cannot read file %s on %s' % (filename, host)
        print e
        os.unlink(filename)
        return False
    else:
        print '****Downloaded ' + filename + ' from ' + host + ' to ' + os.getcwd()
        f.quit()
        return True


if __name__ == "__main__":
    # 下载
    getServerFile(".", "hello.js", "10.110.87.14", 2121, "ctf", "qiyi123456")
    # 上传
    uploadFile(".", "upload_demo.txt", "words.txt", "10.110.87.14", 2121, "ctf", "qiyi123456")
    print '****done'
