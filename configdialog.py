#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#############################################################################
##
## Copyright (C) 2015 无锡中太服务器有限公司 ZOOMNETCOM.
## Vesrsion 1.0
## All rights reserved.
## date: 2015-10-20
## author: lixiaoyi
## python:3.4.3 gcc:4.9.2 sip:4.16.6 PyQt:5.5
##
#############################################################################
from PyQt5.QtCore import QDate, QSize, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QIcon, QPalette, QFont
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDateTimeEdit,
        QDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
        QListView, QListWidget, QListWidgetItem, QPushButton, QSpinBox,
        QStackedWidget, QVBoxLayout, QWidget, QTextEdit,QProgressBar,QMessageBox, QLCDNumber)
from datetime import datetime
import serial, io, time
import  threading
import configdialog_rc
import pexpect

##########################################################
## 定义一个log文件写入的类
##########################################################
class fileWriter(object):
    def __init__(self, filePath):
        self.writer = open(filePath,'a')
        self.writer.write("the date and time of starting test = ")
        self.writer.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        self.writer.write('\n')

    def  writeFullLogFile(self, listLogData):
        '''通过pyserial模块获取的数据会追加一个换行符，
        所以在这里选择去掉以使得看起来日志文件紧凑一些'''
        i=0
        for data in listLogData:
            i = i + 1
            if data == "\n":
                continue
            self.writer.write(data)

    def close(self):
        self.writer.write("the date and time of stopping test = ")
        self.writer.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        self.writer.close()

########################################################
## SSH Class
########################################################
class SSH(object):
    def __init__(self):
        self.ssh = None

    def ssh_cmd(self, ip, passwd, cmd):
        ret = -1
        self.ssh = pexpect.spawn('ssh sysadmin@%s "%s"' % (ip, cmd))
        try:
            i = self.ssh.expect(['password:', 'continue connecting (yes/no)?'], timeout=10)
            if i == 0 :
                self.ssh.sendline(passwd)
            elif i == 1:
                self.ssh.sendline('yes\n')
                self.ssh.expect('password: ')
                self.ssh.sendline(passwd)
            ret = 0
        except pexpect.EOF:
            print("EOF")
            self.ssh.close()
            ret = -1
        except pexpect.TIMEOUT:
            print ("TIMEOUT")
            self.ssh.close()
            ret = -2
        return ret

    def readline(self):
        s = self.ssh.readline()
        s = s.decode('utf-8')
        return s

    def writeline(self, buf):
        self.ssh.sendline(buf)
        #self.ssh.send(buf)

    def expect(self, strData):
        self.ssh.expect(strData)

    def printBefore(self):
        return self.ssh.before

    def close(self):
        self.ssh.close()

#########################################################
## BMC PCBA SSH通讯线程类
#########################################################
class SSHThreader(QThread):
    #create a signal for communicating with logEdit widget 
    sigLogAppend = pyqtSignal(str)

    def __init__(self, logEditAppendHandler):
        QThread.__init__(self)
        self.sigLogAppend.connect(logEditAppendHandler)

        self.ssh = SSH()

    def run(self):
        print("start to run ssh threader now......")
        ret = self.ssh.ssh_cmd('192.168.10.133', 'superuser', 'hwtest -c') 
        print("start to run execute_cmd now......")
        if ret == 0:
            self.execute_cmd('hwtest -c')
        #self.close()
        print("end of ssh test")

    def execute_cmd(self, cmd):
        #self.ssh.sendline(cmd)
        self.ssh.writeline(cmd)
        print("ready to start hwtest -c command")
        while True :
            r = self.ssh.readline()
            print(r)
            self.sigLogAppend.emit(r)
            if "Enter command" in r:
                break
        
        print("send run command to call hwtest -c\n")
        self.ssh.writeline("run\n")
        time.sleep(1)
        while True:
            r=self.ssh.readline()
            #r=r.decode('utf-8')
            print(r)
            self.sigLogAppend.emit(r)
            if "Type (Y/y)" in r:
                self.ssh.writeline("y\n")
                break

    def close(self):
        self.ssh.close()


#########################################################
## BMC Chassis SSH通讯线程类
#########################################################
class BMCChassisSSHThreader(QThread):
    #create a signal for communicating with logEdit widget 
    sigLogAppend = pyqtSignal(str)

    def __init__(self, logEditAppendHandler):
        QThread.__init__(self)
        self.sigLogAppend.connect(logEditAppendHandler)

        self.ssh = SSH()

    def run(self):
        print("start to run ssh threader now......")
        ret = self.ssh.ssh_cmd('192.168.10.133', 'superuser', 'hwtest -c') 
        print("start to run hwtest -c now......")
        if ret == 0:
              self.execute_cmd('hwtest -c')
              #self.execute_cmd2('hwtest -c')
              #new ssh testing code added by lixiaoyi
              #self.waitForSendCMD('#', 'hwtest -c')
              #self.execute_all_code()
              #self.sendCMD('hwtest -c')
              #self.testSpecificItem('1', '1', 'frontPanleLED')
              #self.testSpecificItem('2', '1', 'frontPanleButtons')
              #self.testSpecificItem('3', '1', 'fanSpeed')


        #self.close()
        print("end of ssh test")
        self.close()

    def testSpecificItem(self, strParentItem, strChildItem, strMsg):
        ''' 这里每次选择一个特定的测试小项进行测试，
        通过判断其failures是否存在来确定测试是否通过 '''
        #print("testSpecificItem is calling now...")
        self.waitForSendCMD('Enter command', 'select')
        self.waitForSendCMD('Enter number of suite to select', strParentItem)
        self.waitForSendCMD('Enter command', 'select')
        self.waitForSendCMD('Enter number of test to select', strChildItem)
        self.waitForSendCMD('Enter command', 'f')
        self.getTestResult(strMsg)
        self.sendCMD('up')
        #self.waitForSendCMD('Enter command',b'up')

    def waitForSendCMD(self, strWait, strCMD):
        ''' 等待strWait字符串出现在接收到的字符串中，同时发送strCMD命令给BMC '''
        while True:
            string = self.ssh.readline()
            #过滤掉空行和只带一个换行符的行
            if len(string)>0 and '\n' != string:
                #continue
                #通过发送信号的方式将接收到的字符串发送给GUI线程
                print(string)
                self.sigLogAppend.emit(string)
                #等待指定的字符串出现并发送命令
                if strWait in string:
                    strCMD +='\n'
                    self.ssh.writeline(strCMD)
                    #self.ssh.writeline('\r')
                    time.sleep(1)
                    break
    
    def sendCMD(self, strCMD):
        '''  只是简单地发送单条命令给BMC，不处理后续数据 '''
        self.ssh.writeline(strCMD)
        #self.ssh.writeline('\n')

    def getTestResult(self, strMsg):
        ''' 判断测试结果中是否出现failures，如果无错误，发送信号给界面更新对应的checkbox，
        如果有错误，则线程无需进一步处理，因为后续会由界面程序判定该如何处理本错误 '''
        while True:
            string = self.ssh.readline()
            if len(string)<=0 and '\n'==string:
                continue
            #对于有效数据，通过发送信号的方式将接收到的字符串发送给GUI线程
            print(string)
            self.sigLogAppend.emit(string)
            #判断是否测试成功，成功发送信号给GUI线程，否则忽视
            if 'No failures' in string:
                #self.sigStatus.emit(strMsg)
                break
            elif 'Total Number of Failures' in string: 
                break
            else:
                pass


    def execute_cmd(self, cmd):
        #self.ssh.sendline(cmd)
        #cmd += '\n'
        self.ssh.writeline(cmd)
        print("ready to start hwtest -c command")
        while True :
            r = self.ssh.readline()
            print(r)
            self.sigLogAppend.emit(r)
            if "Enter command" in r:
                break
        
        print("send run command to call hwtest -c\n")
        self.ssh.writeline("run\n")
        time.sleep(1)
        while True:
            r=self.ssh.readline()
            #r=r.decode('utf-8')
            print(r)
            self.sigLogAppend.emit(r)
            if "Type (Y/y)" in r:
                self.ssh.writeline("y\n")
                #break


        print("send failure command to show failures\n")
        #time.sleep(1)
        while True:
            r=self.ssh.readline()
            #r=r.decode('utf-8')
            print(r)
            self.sigLogAppend.emit(r)
            if "Enter command" in r:
                self.ssh.writeline("f\n")


    def execute_cmd2(self, cmd):
        #self.ssh.sendline(cmd)
        print("ready to start hwtest -c command")
        self.ssh.writeline(cmd)
        self.ssh.writeline('\n')
        
        print("Enter Command")
        self.ssh.expect('Enter command')
        print(self.ssh.printBefore().decode('utf-8'))
        time.sleep(1)
        self.ssh.writeline('select')
        self.ssh.writeline('\n')

        print("Enter number of suite to select")
        self.ssh.expect('Enter number of suite to select')
        print(self.ssh.printBefore().decode('utf-8'))
        time.sleep(1)
        self.ssh.writeline('1')
        self.ssh.writeline('\n')

        print("Enter number of test to select")
        self.ssh.expect('Enter number of test to select')
        print(self.ssh.printBefore().decode('utf-8'))
        time.sleep(1)
        self.ssh.writeline('1')
        self.ssh.writeline('\n')

        print("Type (Y/y) means pass or (N/n)")
        self.ssh.expect('Type (Y/y) means pass or (N/n)')
        print(self.ssh.printBefore().decode('utf-8'))
        time.sleep(1)
        self.ssh.writeline('y')
        self.ssh.writeline('\n')

        print("Enter command")
        self.ssh.expect('Enter command')
        print(self.ssh.printBefore().decode('utf-8'))
        time.sleep(1)
        self.ssh.writeline('f')
        self.ssh.writeline('\n')

        print(self.ssh.printBefore().decode('utf-8'))
       




    def close(self):
        self.ssh.close()

    def execute_all_code(self):
        self.ssh.writeline('hwtest -c')

        print("ready to start hwtest -c command")
        while True :
            r = self.ssh.readline()
            print(r)
            self.sigLogAppend.emit(r)
            if "Enter command" in r:
                break
        
        print("send select command to select suites\n")
        #self.ssh.writeline("select\n")
        self.ssh.writeline("select")
        self.ssh.writeline("\n")
        #time.sleep(1)
        while True:
            r=self.ssh.readline()
            #r=r.decode('utf-8')
            print(r)
            self.sigLogAppend.emit(r)
            if "Enter number of suite to select" in r:
                #self.ssh.writeline("1\n")
                break

        print("send select command 1 to select suites 1-1\n")
        #self.ssh.writessh("1\r")
        time.sleep(1)
        while True:
            r=self.ssh.readline()
            #r=r.decode('utf-8')
            print(r)
            self.sigLogAppend.emit(r)
            if "Enter number of suite to select" in r:
                #self.ssh.writeline("1\n")
                break




################################################
## 串口通讯线程类
################################################
class SerialPort(object):
    def __init__(self, devPath, boundRate, timeOut):
        self.ser = serial.Serial(devPath, boundRate, timeout=timeOut)
        self.sio = io.TextIOWrapper(io.BufferedRWPair(self.ser, self.ser))
    
    def readline(self):
        strLine = self.sio.readline()
        return strLine

    def writeBytes(self, byteData):
        self.ser.write(byteData)

    def close(self):
        self.ser.close()

#####################################################
## BIOS PCBA测试模式下的串口通讯线程类
#####################################################
class SerialPortThreader(QThread):
    xsig = pyqtSignal(str)
    sigStatus = pyqtSignal(str)
    sigUpdateLCDNum = pyqtSignal(str)

    def __init__(self, handlerLogEditAppend, handlerStatus, handlerLCD):
        ''' 串口线程中注册了3个信号，用于和GUI进行数据传输 '''
        QThread.__init__(self)
        self.xsig.connect(handlerLogEditAppend)
        self.sigStatus.connect(handlerStatus)
        self.sigUpdateLCDNum.connect(handlerLCD)

        self.ser = SerialPort('/dev/ttyUSB0', 115200, 1)

    def run(self):
        ''' 串口线程类的主逻辑，在这里完成了整个BIOS-PCBA测试的逻辑处理过程 '''
        #ser = SerialPort('/dev/ttyUSB0', 115200, 1)
        #self.sigUpdateLCDNum.emit("0008")
        self.xsig.emit("starting to log information form P8")
        self.waitForSendCMD('Welcome to Petitboot', b'\r')
        self.waitForSendCMD('/ #',  b'cat /proc/binfo')
        self.getMacFromBInfo()
        #send command to run mac-tool to change macaddress

        self.waitForSendCMD('/ #',  b'zpdev_test')

        self.testSpecificItem(b'1', b'1', 'cpuCount')
        self.testSpecificItem(b'1', b'2', 'cpuFreq')
        self.testSpecificItem(b'1', b'3', 'cpuStress')
        self.testSpecificItem(b'4', b'1', 'memTotalSize')
        self.testSpecificItem(b'4', b'2', 'memStream')

        self.testSpecificItem(b'6', b'1', 'pex8748Reg')
        self.testSpecificItem(b'6', b'2', 'pex8748Link')
        self.testSpecificItem(b'7', b'1', 'marvel9230Reg')
        self.testSpecificItem(b'7', b'2', 'marvel9230Link')
        self.testSpecificItem(b'7', b'3', 'marvel9230Func')

        self.testSpecificItem(b'8', b'1', 'bcm5718Reg')
        self.testSpecificItem(b'8', b'2', 'bcm5718Link')
        self.testSpecificItem(b'10', b'1', 'ti7340Reg')
        self.testSpecificItem(b'10', b'2', 'ti7340Link')
        self.testSpecificItem(b'10', b'3', 'ti7340Func')

        self.testSpecificItem(b'15', b'1', 'intelI350Reg')
        self.testSpecificItem(b'15', b'2', 'intelI350Link')
        self.testSpecificItem(b'15', b'3', 'intelI350Func')
        self.testSpecificItem(b'17', b'1', 'intelI82599Reg')
        self.testSpecificItem(b'17', b'2', 'intelI82599Link')

        self.testSpecificItem(b'17', b'3', 'intelI82599Func')
        self.testSpecificItem(b'18', b'1', 'lpcRtc')
        self.testSpecificItem(b'19', b'1', 'ast2400Reg')
        self.testSpecificItem(b'19', b'2', 'ast2400Link')
        self.testSpecificItem(b'20', b'1', 'gk107Reg')
        self.testSpecificItem(b'20', b'2', 'gk107Link')

        self.ser.close()

        self.xsig.emit("login to P8 BIOS successfully")
        self.sigStatus.emit('END')

    def testSpecificItem(self, byteParentItem, byteChildItem, strMsg):
        ''' 这里每次选择一个特定的测试小项进行测试，
        通过判断其failures是否存在来确定测试是否通过 '''

        self.waitForSendCMD('Enter command', b'select')
        self.waitForSendCMD('Enter number of suite to select', byteParentItem)
        self.waitForSendCMD('Enter command', b'select')
        self.waitForSendCMD('Enter number of test to select', byteChildItem)
        #self.waitForSendCMD('Enter command', b'run')
        self.waitForSendCMD('Enter command', b'f')
        self.getTestResult(strMsg)
        self.sendCMD(b'up')
        #self.waitForSendCMD('Enter command',b'up')

    def waitForSendCMD(self, strWait, byteCMD):
        ''' 等待strWait字符串出现在接收到的字符串中，同时发送byteCMD命令给P8,
        注意发送给P8的数据是byte类型，不是str类型的 '''
        while True:
            string = self.ser.readline()
            if len(string)>0 and string != '\n':
                print(string)
                self.xsig.emit(string)
                if strWait in string:
                    self.ser.writeBytes(byteCMD)
                    self.ser.writeBytes(b'\r')
                    break

    def getTestResult(self, strMsg):
        ''' 判断测试结果中是否出现failures，如果无错误，发送信号给界面更新对应的checkbox，
        如果有错误，则线程无需进一步处理，因为后续会由界面程序判定该如何处理本错误 '''
        while True:
            string = self.ser.readline()
            if len(string)>0 and string != '\n':
                print(string)
                self.xsig.emit(string)
                if 'No failures' in string:
                    self.sigStatus.emit(strMsg)
                    break
                elif 'Total Number of Failures' in string: 
                    break
                else:
                    pass
                    
    def sendCMD(self, strCMD):
        self.ser.writeBytes(strCMD)
        self.ser.writeBytes(b'\r')

    def getMacFromBInfo(self):
        ''' 获取binfo中的mac地址，然后通过切片的方式提取后3字节做加1操作, 
        BMC的网卡mac，加2后是BIOS mac地址，
        此外，默认mac地址的前3字节是厂商信息，我们是0008D2 '''
        while True:
            string = self.ser.readline()
            if len(string)>0 and string != '\n':
                print(string)
                self.xsig.emit(string)
                if 'mac:00-08-d2' in string:
                    #get mac, ex: mac:00-08-d2-ed-fb-ab (0008d2edfbab)
                    self.bmcMac = string[-14:-2]
                    print('self.bmcMac = %s' % self.bmcMac)
                    # 补5个0是因为当后3字节数值较小时，如000001，转换为int后为1，
                    # 不足6个数字，所以需要补偿5个00000，否则切片时位数不足会出错
                    newmac = '00000' + hex(int(self.bmcMac[-6:], 16) + 2)[2:]
                    self.biosMac = '00:08:d2:'
                    self.biosMac += newmac[-6:-4]
                    self.biosMac += ':'
                    self.biosMac += newmac[-4:-2]
                    self.biosMac += ':'
                    self.biosMac += newmac[-2:]
                    #for display in LogEdit widget
                    self.xsig.emit(self.biosMac.upper())
                    break


#####################################################
## OS Chassis 整机测试模式下的串口通讯线程类
#####################################################
class OSChassisSerialPortThreader(QThread):
    xsig = pyqtSignal(str)
    sigStatus = pyqtSignal(str)
    sigUpdateLCDNum = pyqtSignal(str)

    def __init__(self, handlerLogEditAppend, handlerStatus, handlerLCD):
        ''' 串口线程中注册了3个信号，用于和GUI进行数据传输 '''
        QThread.__init__(self)
        self.xsig.connect(handlerLogEditAppend)
        self.sigStatus.connect(handlerStatus)
        self.sigUpdateLCDNum.connect(handlerLCD)

        self.ser = SerialPort('/dev/ttyUSB0', 115200, 1)

    def run(self):
        ''' 串口线程类的主逻辑，在这里完成了整个BIOS-PCBA测试的逻辑处理过程 '''
        #ser = SerialPort('/dev/ttyUSB0', 115200, 1)
        #self.sigUpdateLCDNum.emit("0008")
        self.xsig.emit("starting to log information form P8")
        self.waitForSendCMD('Welcome to Petitboot', b'\r')
        self.waitForSendCMD('/ #',  b'cat /proc/binfo')
        self.getMacFromBInfo()
        #send command to run mac-tool to change macaddress

        self.waitForSendCMD('/ #',  b'zpdev_test')

        self.testSpecificItem(b'1', b'1', 'cpuCount')
        self.testSpecificItem(b'1', b'2', 'cpuFreq')
        self.testSpecificItem(b'1', b'3', 'cpuStress')
        self.testSpecificItem(b'4', b'1', 'memTotalSize')
        self.testSpecificItem(b'4', b'2', 'memStream')

        self.testSpecificItem(b'6', b'1', 'pex8748Reg')
        self.testSpecificItem(b'6', b'2', 'pex8748Link')
        self.testSpecificItem(b'7', b'1', 'marvel9230Reg')
        self.testSpecificItem(b'7', b'2', 'marvel9230Link')
        self.testSpecificItem(b'7', b'3', 'marvel9230Func')

        self.testSpecificItem(b'8', b'1', 'bcm5718Reg')
        self.testSpecificItem(b'8', b'2', 'bcm5718Link')
        self.testSpecificItem(b'10', b'1', 'ti7340Reg')
        self.testSpecificItem(b'10', b'2', 'ti7340Link')
        self.testSpecificItem(b'10', b'3', 'ti7340Func')

        self.testSpecificItem(b'15', b'1', 'intelI350Reg')
        self.testSpecificItem(b'15', b'2', 'intelI350Link')
        self.testSpecificItem(b'15', b'3', 'intelI350Func')
        self.testSpecificItem(b'17', b'1', 'intelI82599Reg')
        self.testSpecificItem(b'17', b'2', 'intelI82599Link')

        self.testSpecificItem(b'17', b'3', 'intelI82599Func')
        self.testSpecificItem(b'18', b'1', 'lpcRtc')
        self.testSpecificItem(b'19', b'1', 'ast2400Reg')
        self.testSpecificItem(b'19', b'2', 'ast2400Link')
        self.testSpecificItem(b'20', b'1', 'gk107Reg')
        self.testSpecificItem(b'20', b'2', 'gk107Link')

        self.ser.close()

        self.xsig.emit("login to P8 BIOS successfully")
        self.sigStatus.emit('END')

    def testSpecificItem(self, byteParentItem, byteChildItem, strMsg):
        ''' 这里每次选择一个特定的测试小项进行测试，
        通过判断其failures是否存在来确定测试是否通过 '''

        self.waitForSendCMD('Enter command', b'select')
        self.waitForSendCMD('Enter number of suite to select', byteParentItem)
        self.waitForSendCMD('Enter command', b'select')
        self.waitForSendCMD('Enter number of test to select', byteChildItem)
        #self.waitForSendCMD('Enter command', b'run')
        self.waitForSendCMD('Enter command', b'f')
        self.getTestResult(strMsg)
        self.sendCMD(b'up')
        #self.waitForSendCMD('Enter command',b'up')

    def waitForSendCMD(self, strWait, byteCMD):
        ''' 等待strWait字符串出现在接收到的字符串中，同时发送byteCMD命令给P8,
        注意发送给P8的数据是byte类型，不是str类型的 '''
        while True:
            string = self.ser.readline()
            if len(string)>0 and string != '\n':
                print(string)
                self.xsig.emit(string)
                if strWait in string:
                    self.ser.writeBytes(byteCMD)
                    self.ser.writeBytes(b'\r')
                    break

    def getTestResult(self, strMsg):
        ''' 判断测试结果中是否出现failures，如果无错误，发送信号给界面更新对应的checkbox，
        如果有错误，则线程无需进一步处理，因为后续会由界面程序判定该如何处理本错误 '''
        while True:
            string = self.ser.readline()
            if len(string)>0 and string != '\n':
                print(string)
                self.xsig.emit(string)
                if 'No failures' in string:
                    self.sigStatus.emit(strMsg)
                    break
                elif 'Total Number of Failures' in string: 
                    break
                else:
                    pass
                    
    def sendCMD(self, strCMD):
        self.ser.writeBytes(strCMD)
        self.ser.writeBytes(b'\r')

    def getMacFromBInfo(self):
        ''' 获取binfo中的mac地址，然后通过切片的方式提取后3字节做加1操作, 
        BMC的网卡mac，加2后是BIOS mac地址，
        此外，默认mac地址的前3字节是厂商信息，我们是0008D2 '''
        while True:
            string = self.ser.readline()
            if len(string)>0 and string != '\n':
                print(string)
                self.xsig.emit(string)
                if 'mac:00-08-d2' in string:
                    #get mac, ex: mac:00-08-d2-ed-fb-ab (0008d2edfbab)
                    self.bmcMac = string[-14:-2]
                    print('self.bmcMac = %s' % self.bmcMac)
                    # 补5个0是因为当后3字节数值较小时，如000001，转换为int后为1，
                    # 不足6个数字，所以需要补偿5个00000，否则切片时位数不足会出错
                    newmac = '00000' + hex(int(self.bmcMac[-6:], 16) + 2)[2:]
                    self.biosMac = '00:08:d2:'
                    self.biosMac += newmac[-6:-4]
                    self.biosMac += ':'
                    self.biosMac += newmac[-4:-2]
                    self.biosMac += ':'
                    self.biosMac += newmac[-2:]
                    #for display in LogEdit widget
                    self.xsig.emit(self.biosMac.upper())
                    break


###############################################################
##BIOS-PCBA主板测试主界面
###############################################################
class BIOSPCBAPage(QWidget):
    def __init__(self, parent=None):
        ''' 构造函数中生成了BIOS-PCBA测试的主界面，
        具体的子控件的生成及布局可以运行程序并查看具体的显示效果 '''
        super(BIOSPCBAPage, self).__init__(parent)
        #用于记录已测机器总数，测试通过机器总数，当前机器测试通过数的变量
        self.setTestedCount  = set()
        self.setPassedCount = set()
        self.currentSuccessedCount = 0

        #如下是界面上控件的定义和布局的设置
        configGroup = QGroupBox("请在这里录入条码信息--------------BIOS PCBA测试")
        serverLabel = QLabel("条码录入")
        self.serialNumEdit = QLineEdit()
        self.serialNumEdit.setFont(QFont("Times", 12))
        self.serialNumEdit.setFixedWidth(300) 
        self.startBtn = QPushButton("开始测试")
        self.startBtn.setFixedWidth(80)

        #serverCombo = QComboBox()
        #serverCombo.addItem("zoomnetcom")
        #serverCombo.addItem("USI")
        #serverCombo.addItem("RED POWER8")

        updateGroup = QGroupBox("各子项当前的测试状态")
        self.cpuCountCheckBox = QCheckBox("1-CPU数量测试")
        self.cpuFreqCheckBox = QCheckBox("2-CPU频率测试")
        self.cpuStressCheckBox = QCheckBox("3-CPU压力测试")

        self.memTotalCheckBox = QCheckBox("4-内存容量测试")
        self.memStreamCheckBox = QCheckBox("5-内存吞吐测试")

        self.pex8748RegCheckBox = QCheckBox("6-PEX8748寄存器测试")
        self.pex8748LinkCheckBox = QCheckBox("7-PEX8748 Link测试")

        self.marvel9230RegCheckBox = QCheckBox("8-Marvel9230寄存器测试")
        self.marvel9230LinkCheckBox = QCheckBox("9-Marvel9230 Link测试")
        self.marvel9230FuncCheckBox = QCheckBox("10-Marvel9230功能测试")

        self.bcm5718RegCheckBox = QCheckBox("11-BCM5718寄存器测试")
        self.bcm5718LinkCheckBox = QCheckBox("12-BCM5718 Link测试")

        self.ti7340RegCheckBox = QCheckBox("13-TI7340寄存器测试")
        self.ti7340LinkCheckBox = QCheckBox("14-TI7340 Link测试")
        self.ti7340FuncCheckBox = QCheckBox("15-TI7340 功能测试")

        self.intelI350RegCheckBox = QCheckBox("16-I350寄存器测试")
        self.intelI350LinkCheckBox = QCheckBox("17-I350 Link测试")
        self.intelI350FuncCheckBox = QCheckBox("18-I350 功能测试")

        self.intelI82599RegCheckBox = QCheckBox("19-I82599寄存器测试")
        self.intelI82599LinkCheckBox = QCheckBox("20-I82599 Link测试")
        self.intelI82599FuncCheckBox = QCheckBox("21-I82599 功能测试")

        self.lpcRtcCheckBox = QCheckBox("22-RTC 测试")

        self.ast2400RegCheckBox = QCheckBox("23-ast2400寄存器测试")
        self.ast2400LinkCheckBox = QCheckBox("24-ast2400 Link测试")

        self.gk107RegCheckBox = QCheckBox("25-GK107寄存器测试")
        self.gk107LinkCheckBox = QCheckBox("26-GK107 Link测试")

        progressGroup = QGroupBox("当前测试进度")
        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(100)

        #LCD number
        counterLCDNumGroup = QGroupBox("已测机器总数  测试通过机器数  本次异常数")
        self.CounterLCDNumber = QLCDNumber()
        self.CounterLCDNumber.setDigitCount(5)
        lcdpat = self.CounterLCDNumber.palette()
        lcdpat.setColor(QPalette.Normal,QPalette.WindowText,Qt.white)
        self.CounterLCDNumber.setPalette(lcdpat)

        self.CounterLCDNumber.setSegmentStyle(QLCDNumber.Flat)
        self.CounterLCDNumber.setStyleSheet("background-color: blue")
        #self.CounterLCDNumber.resize(150, 200)
        self.CounterLCDNumber.display('0000')

        self.CounterLCDNumber2 = QLCDNumber()
        self.CounterLCDNumber2.setDigitCount(5)
        lcdpat2 = self.CounterLCDNumber2.palette()
        lcdpat2.setColor(QPalette.Normal,QPalette.WindowText,Qt.white)
        self.CounterLCDNumber2.setPalette(lcdpat2)

        self.CounterLCDNumber2.setSegmentStyle(QLCDNumber.Flat)
        self.CounterLCDNumber2.setStyleSheet("background-color: green")
        #self.CounterLCDNumber2.resize(150, 200)
        self.CounterLCDNumber2.display('0000')

        self.CounterLCDNumber3 = QLCDNumber()
        self.CounterLCDNumber3.setDigitCount(5)
        lcdpat = self.CounterLCDNumber.palette()
        lcdpat.setColor(QPalette.Normal,QPalette.WindowText,Qt.yellow)
        self.CounterLCDNumber3.setPalette(lcdpat)

        self.CounterLCDNumber3.setSegmentStyle(QLCDNumber.Flat)
        self.CounterLCDNumber3.setStyleSheet("background-color: red")
        #self.CounterLCDNumber.resize(150, 200)
        self.CounterLCDNumber3.display('0000')

        self.hintLabel=QLabel("<font color='#0000ff' size=15 background-color='#00ff00'>&nbsp;</font>")

        counterLCDLayout = QHBoxLayout()
        counterLCDLayout.addWidget(self.CounterLCDNumber)
        counterLCDLayout.addWidget(self.CounterLCDNumber2)
        counterLCDLayout.addWidget(self.CounterLCDNumber3)
        counterLCDLayout.addWidget(self.hintLabel)
        counterLCDLayout.addStretch()
        counterLCDNumGroup.setLayout(counterLCDLayout)
        
        cpuLayout = QVBoxLayout()
        cpuLayout.addWidget(self.cpuCountCheckBox)
        cpuLayout.addWidget(self.cpuFreqCheckBox)
        cpuLayout.addWidget(self.cpuStressCheckBox)
        #updateGroup.setLayout(updateLayout)
        cpuLayout.addWidget(self.memTotalCheckBox)
        cpuLayout.addWidget(self.memStreamCheckBox)

        #memLayout = QVBoxLayout()
        #memLayout.addWidget(memTotalCheckBox)
        #memLayout.addWidget(memStreamCheckBox)

        pex8748Layout = QVBoxLayout()
        pex8748Layout.addWidget(self.pex8748RegCheckBox)
        pex8748Layout.addWidget(self.pex8748LinkCheckBox)

        #marvel9230Layout = QVBoxLayout()
        pex8748Layout.addWidget(self.marvel9230RegCheckBox)
        pex8748Layout.addWidget(self.marvel9230LinkCheckBox)
        pex8748Layout.addWidget(self.marvel9230FuncCheckBox)

        bcm5718Layout = QVBoxLayout()
        bcm5718Layout.addWidget(self.bcm5718RegCheckBox)
        bcm5718Layout.addWidget(self.bcm5718LinkCheckBox)

        #ti7340Layout = QVBoxLayout()
        bcm5718Layout.addWidget(self.ti7340RegCheckBox)
        bcm5718Layout.addWidget(self.ti7340LinkCheckBox)
        bcm5718Layout.addWidget(self.ti7340FuncCheckBox)

        i350Layout = QVBoxLayout()
        i350Layout.addWidget(self.intelI350RegCheckBox)
        i350Layout.addWidget(self.intelI350LinkCheckBox)
        i350Layout.addWidget(self.intelI350FuncCheckBox)
        i350Layout.addWidget(self.intelI82599RegCheckBox)
        i350Layout.addWidget(self.intelI82599LinkCheckBox)

        #i82599Layout = QVBoxLayout()
        #i82599Layout.addWidget(intelI82599RegCheckBox)
        #i82599Layout.addWidget(intelI82599LinkCheckBox)
        #i82599Layout.addWidget(intelI82599FuncCheckBox)

        lpcRtcLayout = QVBoxLayout()
        lpcRtcLayout.addWidget(self.intelI82599FuncCheckBox)
        lpcRtcLayout.addWidget(self.lpcRtcCheckBox)
        lpcRtcLayout.addWidget(self.ast2400RegCheckBox)
        lpcRtcLayout.addWidget(self.ast2400LinkCheckBox)
        lpcRtcLayout.addWidget(self.gk107RegCheckBox)
        
        gk107Layout = QVBoxLayout()
        gk107Layout.addWidget(self.gk107LinkCheckBox)

        progressLayout = QHBoxLayout()
        progressLayout.addWidget(self.progressBar)
        progressGroup.setLayout(progressLayout)

        logEditGroup = QGroupBox("显示从串口接收到的所有Power8打印数据")
        self.logEdit = QTextEdit()
        self.logEdit.setReadOnly(True)
        #logEdit.setLineWrapMode(QTextEdit.NoWrap)
        #logEdit.setPlainText("Log info 1 from Redpower8 serial port")
        self.logEdit.append("显示从串口接收到的所有Power8 Shell打印数据：")
        self.logEdit.append("Log info  from Redpower8 serial port")

        logEditLayout = QHBoxLayout()
        logEditLayout.addWidget(self.logEdit)
        logEditGroup.setLayout(logEditLayout)


        updateHLayout = QHBoxLayout()
        updateHLayout.addLayout(cpuLayout)
        #updateHLayout.addLayout(memLayout)
        updateHLayout.addLayout(pex8748Layout)
        #updateHLayout.addLayout(marvel9230Layout)
        updateHLayout.addLayout(bcm5718Layout)
        updateHLayout.addLayout(i350Layout )
        updateHLayout.addLayout(lpcRtcLayout)
        updateHLayout.addLayout(gk107Layout)
        updateGroup.setLayout(updateHLayout)

        serverLayout = QHBoxLayout()
        serverLayout.addWidget(serverLabel)
        serverLayout.addWidget(self.serialNumEdit)
        serverLayout.addWidget(self.startBtn)
        serverLayout.addStretch()

        configLayout = QVBoxLayout()
        configLayout.addLayout(serverLayout)
        configGroup.setLayout(configLayout)

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(configGroup)
        mainLayout.addWidget(updateGroup)
        mainLayout.addWidget(counterLCDNumGroup)
        mainLayout.addWidget(progressGroup)
        mainLayout.addWidget(logEditGroup)
        #mainLayout.addStretch(1)
        self.setLayout(mainLayout)

        self.startBtn.clicked.connect(self.startBtnFunction)
        

    def startBtnFunction(self):
        #获取编辑框上的条码信息
        self.usiSN = self.serialNumEdit.text()
        if len(self.usiSN) != 27 or self.usiSN[0:3] != 'USI':
            rt = QMessageBox.information(self, "USI条码比对", "错误：条码不是27位或者不是以USI开头",  QMessageBox.Yes)
            return

        #启动串口线程，同时将需要和串口类中对应的信号关联的槽函数注册进去
        print("read to start threading module to process data received from P8")
        self.threader = SerialPortThreader(self.onMsgAppendLog, self.onMsgUpdateStatus, self.onMsgUpdateLCDNumber)
        self.threader.start()
        #初始化进度条为0
        self.progressBar.setValue(0)

        #创建日志记录文档对象, 日志文件以编辑框中输入的USI条码命名
        #self.fileWriter = fileWriter('./bios_pcba.log')
        self.usiSN +='.log'
        self.fileWriter = fileWriter(self.usiSN)

        #用于暂时存储串口收集的信息, 最后该list中记录的P8串口输出的所有数据都会写到上面的日志文件中
        self.logList = []
        #屏蔽‘开始测试’按钮，直到测试完成后再恢复它，以免反复连续点击造成意外
        self.startBtn.setEnabled(False)

        #clear checkbox status
        self.cpuCountCheckBox.setChecked(False)
        self.cpuFreqCheckBox.setChecked(False)
        self.cpuStressCheckBox.setChecked(False)
        self.memTotalCheckBox.setChecked(False)
        self.memStreamCheckBox.setChecked(False)
        self.pex8748RegCheckBox.setChecked(False)
        self.pex8748LinkCheckBox.setChecked(False)
        self.marvel9230RegCheckBox.setChecked(False)
        self.marvel9230LinkCheckBox.setChecked(False)
        self.marvel9230FuncCheckBox.setChecked(False)
        self.bcm5718RegCheckBox.setChecked(False)
        self.bcm5718LinkCheckBox.setChecked(False)
        self.ti7340RegCheckBox.setChecked(False)
        self.ti7340LinkCheckBox.setChecked(False)
        self.ti7340FuncCheckBox.setChecked(False)
        self.intelI350RegCheckBox.setChecked(False)
        self.intelI350LinkCheckBox.setChecked(False)
        self.intelI350FuncCheckBox.setChecked(False)
        self.intelI82599RegCheckBox.setChecked(False)
        self.intelI82599LinkCheckBox.setChecked(False)
        self.intelI82599FuncCheckBox.setChecked(False)
        self.lpcRtcCheckBox.setChecked(False)
        self.ast2400RegCheckBox.setChecked(False)
        self.ast2400LinkCheckBox.setChecked(False)
        self.gk107RegCheckBox.setChecked(False)
        self.gk107LinkCheckBox.setChecked(False)

        self.CounterLCDNumber3.display('0')
        self.currentSuccessedCount = 0
        self.hintLabel.setText("<font color='#0000ff' size=15 background-color='#00ff00'>&nbsp;</font>")
        #here to add more code if necessary

    @pyqtSlot(str)
    def onMsgUpdateLCDNumber(self, strmsg):
        self.CounterLCDNumber3.display(strmsg)

    @pyqtSlot(str)
    def onMsgAppendLog(self, strmsg):
        self.logEdit.append(strmsg)
        self.logList.append(strmsg)

    @pyqtSlot(str)
    def onMsgUpdateStatus(self, strmsg):
        if 'cpuCount' == strmsg:
            self.cpuCountCheckBox.setChecked(True)
            self.progressBar.setValue(4)
            self.currentSuccessedCount += 1
        elif 'cpuFreq' == strmsg:
            self.cpuFreqCheckBox.setChecked(True)
            self.progressBar.setValue(8)
            self.currentSuccessedCount += 1
        elif 'cpuStress' == strmsg:
            self.cpuStressCheckBox.setChecked(True)
            self.progressBar.setValue(12)
            self.currentSuccessedCount += 1
        elif 'memTotalSize' == strmsg:
            self.memTotalCheckBox.setChecked(True)
            self.progressBar.setValue(16)
            self.currentSuccessedCount += 1
        elif 'memStream' == strmsg:
            self.memStreamCheckBox.setChecked(True)
            self.progressBar.setValue(20)
            self.currentSuccessedCount += 1
        elif 'pex8748Reg' == strmsg:
            self.pex8748RegCheckBox.setChecked(True)
            self.progressBar.setValue(24)
            self.currentSuccessedCount += 1
        elif 'pex8748Link' == strmsg:
            self.pex8748LinkCheckBox.setChecked(True)
            self.progressBar.setValue(28)
            self.currentSuccessedCount += 1
        elif 'marvel9230Reg' == strmsg:
            self.marvel9230RegCheckBox.setChecked(True)
            self.progressBar.setValue(32)
            self.currentSuccessedCount += 1
        elif 'marvel9230Link' == strmsg:
            self.marvel9230LinkCheckBox.setChecked(True)
            self.progressBar.setValue(36)
            self.currentSuccessedCount += 1
        elif 'marvel9230Func' == strmsg:
            self.marvel9230FuncCheckBox.setChecked(True)
            self.progressBar.setValue(40)
            self.currentSuccessedCount += 1
        elif 'bcm5718Reg' == strmsg:
            self.bcm5718RegCheckBox.setChecked(True)
            self.progressBar.setValue(44)
            self.currentSuccessedCount += 1
        elif 'bcm5718Link' == strmsg:
            self.bcm5718LinkCheckBox.setChecked(True)
            self.progressBar.setValue(48)
            self.currentSuccessedCount += 1
        elif 'ti7340Reg' == strmsg:
            self.ti7340RegCheckBox.setChecked(True)
            self.progressBar.setValue(52)
            self.currentSuccessedCount += 1
        elif 'ti7340Link' == strmsg:
            self.ti7340LinkCheckBox.setChecked(True)
            self.progressBar.setValue(56)
            self.currentSuccessedCount += 1
        elif 'ti7340Func' == strmsg:
            self.ti7340FuncCheckBox.setChecked(True)
            self.progressBar.setValue(60)
            self.currentSuccessedCount += 1
        elif 'intelI350Reg' == strmsg:
            self.intelI350RegCheckBox.setChecked(True)
            self.progressBar.setValue(64)
            self.currentSuccessedCount += 1
        elif 'intelI350Link' == strmsg:
            self.intelI350LinkCheckBox.setChecked(True)
            self.progressBar.setValue(64)
            self.currentSuccessedCount += 1
        elif 'intelI350Func' == strmsg:
            self.intelI350FuncCheckBox.setChecked(True)
            self.progressBar.setValue(68)
            self.currentSuccessedCount += 1
        elif 'intelI82599Reg' == strmsg:
            self.intelI82599RegCheckBox.setChecked(True)
            self.progressBar.setValue(72)
            self.currentSuccessedCount += 1
        elif 'intelI82599Link' == strmsg:
            self.intelI82599LinkCheckBox.setChecked(True)
            self.progressBar.setValue(76)
            self.currentSuccessedCount += 1
        elif 'intelI82599Func' == strmsg:
            self.intelI82599FuncCheckBox.setChecked(True)
            self.progressBar.setValue(80)
            self.currentSuccessedCount += 1
        elif 'lpcRtc' == strmsg:
            self.lpcRtcCheckBox.setChecked(True)
            self.progressBar.setValue(84)
            self.currentSuccessedCount += 1
        elif 'ast2400Reg' == strmsg:
            self.ast2400RegCheckBox.setChecked(True)
            self.progressBar.setValue(88)
            self.currentSuccessedCount += 1
        elif 'ast2400Link' == strmsg:
            self.ast2400LinkCheckBox.setChecked(True)
            self.progressBar.setValue(92)
            self.currentSuccessedCount += 1
        elif 'gk107Reg' == strmsg:
            self.gk107RegCheckBox.setChecked(True)
            self.progressBar.setValue(96)
            self.currentSuccessedCount += 1
        elif 'gk107Link' == strmsg:
            self.gk107LinkCheckBox.setChecked(True)
            self.progressBar.setValue(100)
            self.currentSuccessedCount += 1
        elif 'END' == strmsg:
            self.progressBar.setValue(100)
            #最后写日志文件
            self.fileWriter.writeFullLogFile(self.logList)
            self.fileWriter.close()
            #恢复‘开始测试’按钮
            self.startBtn.setEnabled(True)
            #根据测试结果更新LCD显示控件上的统计数字
            snUSI = self.serialNumEdit.text()
            errorsCount = 26-self.currentSuccessedCount
            if 0 == errorsCount:
                #testing successed, 把测试的机器的条码信息记录到对应set集合中
                self.setTestedCount.add(snUSI)
                self.setPassedCount.add(snUSI)
                self.CounterLCDNumber.display(str(len(self.setTestedCount)))
                self.CounterLCDNumber2.display(str(len(self.setPassedCount)))
                self.CounterLCDNumber3.display("0")
                #self.hintLabel.setText("<font color='#0000ff' size=15>TEST PASSED</font>")
            else:
                #testing failed, 设置测试的统计信息到LCD显示控件上，测试通过数不添加到set中
                self.setTestedCount.add(snUSI)
                self.CounterLCDNumber.display(str(len(self.setTestedCount)))
                self.CounterLCDNumber2.display(str(len(self.setPassedCount)))
                self.CounterLCDNumber3.display(str(errorsCount))
                #self.hintLabel.setText("<font color='#ff0000' size=15>TEST FAILED</font>")
                QMessageBox.information(self, "PCBA测试", "错误：测试失败",  QMessageBox.Yes)
        else:
            pass

###############################################################
## note: BMC-PCBA测试主图形用户界面
###############################################################
class BmcPcbaPage(QWidget):
    def __init__(self, parent=None):
        super(BmcPcbaPage, self).__init__(parent)
        #1 定义条码录入lineedit控件
        serialNumGroup = QGroupBox("请在这里录入条码信息--------------BMC PCBA测试")
        usiSNLabel = QLabel("USI条码")
        self.usiSerialNumLineEdit = QLineEdit()
        self.usiSerialNumLineEdit.setFixedWidth(240) 
        zoomSNLabel = QLabel("中太条码")
        self.zoomSerialNumLineEdit = QLineEdit()
        self.zoomSerialNumLineEdit.setFixedWidth(240) 
        macLabel = QLabel("MAC")
        self.macLineEdit = QLineEdit()
        self.macLineEdit.setFixedWidth(240) 
        startBtn = QPushButton("开始测试")
        startBtn.setFixedWidth(80)

        #2 定义状态显示控件CheckBox集合
        testItemCheckGroup = QGroupBox("各子项当前的测试状态")
        self.rtcCheckBox = QCheckBox("1-RTC测试")
        self.setMacCheckBox = QCheckBox("2-MAC设置")
        self.setZoomSNCheckBox = QCheckBox("3-ZOOM SN设置")
        self.saveLogFileCheckBox = QCheckBox("4-保存日志文件")
        self.setRTCTimeCheckBox = QCheckBox("5-设置RTC时间")
        self.verifyBMCFirmwareCheckbox = QCheckBox("6-BMC固件校验")
        self.verifyBIOSFirmwareCheckbox = QCheckBox("7-BIOS固件校验")
        self.verifyFPGAFirmwareCheckbox = QCheckBox("8-FPGA固件校验")
        self.upDownRJ45Checkbox = QCheckBox("9-RJ45启停测试")
        self.beeperTestCheckbox = QCheckBox("10-蜂鸣器测试")
        self.bmcCPUCheckbox = QCheckBox("11-BMC CPU")
        self.bmcFlash1Checkbox = QCheckBox("12-BMC Flash1")
        self.bmcFlash2Checkbox = QCheckBox("13-BMC Flash2")
        self.BIOSFlash1Checkbox = QCheckBox("14-BIOS Flash1")
        self.BIOSFlash2Checkbox = QCheckBox("15-BIOS Flash2")
        self.nvramCheckbox = QCheckBox("16-NVRAM")
        self.nicRJ45Checkbox = QCheckBox("17-NIC RJ45")
        self.phyRJ45Checkbox = QCheckBox("18-PHY RJ45")
        self.fpgaCheckbox = QCheckBox("19-FPGA")
        self.poweronCheckbox = QCheckBox("20-Power On")
        self.memoryCheckbox  = QCheckBox("21-Memory")
        self.adcCheckbox = QCheckBox("22-ADC")
        self.i2cCheckbox = QCheckBox("23-I2C")
        self.buzzerCheckbox = QCheckBox("24-buzzer")
        self.MotherBoardLED = QCheckBox("25-MB LED")



        #3定义显示当前测试项目情况的LCD数字显示控件
        counterLCDNumGroup = QGroupBox("    已测机器数    测试完成数  本次测试异常数")
        self.CounterLCDNumber = QLCDNumber()
        self.CounterLCDNumber.setDigitCount(5)
        lcdpat = self.CounterLCDNumber.palette()
        lcdpat.setColor(QPalette.Normal,QPalette.WindowText,Qt.white)
        self.CounterLCDNumber.setPalette(lcdpat)
        self.CounterLCDNumber.setSegmentStyle(QLCDNumber.Flat)
        self.CounterLCDNumber.setStyleSheet("background-color: blue")
        self.CounterLCDNumber.display('0000')

        self.passedLCDNumber = QLCDNumber()
        self.passedLCDNumber.setDigitCount(5)
        lcdpat = self.passedLCDNumber.palette()
        lcdpat.setColor(QPalette.Normal,QPalette.WindowText,Qt.white)
        self.passedLCDNumber.setPalette(lcdpat)
        self.passedLCDNumber.setSegmentStyle(QLCDNumber.Flat)
        self.passedLCDNumber.setStyleSheet("background-color: green")
        self.passedLCDNumber.display('0000')

        self.errorLCDNumber = QLCDNumber()
        self.errorLCDNumber.setDigitCount(5)
        lcdpat = self.errorLCDNumber.palette()
        lcdpat.setColor(QPalette.Normal,QPalette.WindowText,Qt.yellow)
        self.errorLCDNumber.setPalette(lcdpat)
        self.errorLCDNumber.setSegmentStyle(QLCDNumber.Flat)
        self.errorLCDNumber.setStyleSheet("background-color: red")
        self.errorLCDNumber.display('0000')
        #设置提示信息的字体，通过这个字体同时扩大了LCD显示字体的大小
        self.hintLabel=QLabel("<font color='#0000ff' size=15 background-color='#00ff00'>&nbsp;</font>")

        #定义当前测试进度控件
        progressGroup = QGroupBox("当前测试进度")
        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(100)

        #显示从串口接收到的所有Power8打印数据控件
        logEditGroup = QGroupBox("显示从串口接收到的所有Power8打印数据")
        self.logEdit = QTextEdit()
        self.logEdit.setReadOnly(True)
        self.logEdit.append("显示从串口接收到的所有Power8 Shell打印数据")
        self.logEdit.append("Log info  from the serial port of the Redpower8 ")

        #定义条码录入lineedit控件的布局
        serialNumLayout = QHBoxLayout()
        serialNumLayout.addWidget(usiSNLabel)
        serialNumLayout.addWidget(self.usiSerialNumLineEdit)
        serialNumLayout.addWidget(zoomSNLabel)
        serialNumLayout.addWidget(self.zoomSerialNumLineEdit)
        serialNumLayout.addWidget(macLabel)
        serialNumLayout.addWidget(self.macLineEdit)
        serialNumLayout.addWidget(startBtn)
        serialNumLayout.addStretch(1)
        serialNumGroup.setLayout(serialNumLayout)

        #定义Status CheckBox控件的布局, 把各个checkbox控件添加到对应的布局中, 每5个一组
        statusWholeLayout = QHBoxLayout()
        statusCheckLayout1= QVBoxLayout()
        statusCheckLayout1.addWidget(self.rtcCheckBox)
        statusCheckLayout1.addWidget(self.setMacCheckBox)
        statusCheckLayout1.addWidget(self.setZoomSNCheckBox)
        statusCheckLayout1.addWidget(self.saveLogFileCheckBox)
        statusCheckLayout1.addWidget(self.setRTCTimeCheckBox)

        statusCheckLayout2 = QVBoxLayout()
        statusCheckLayout2.addWidget(self.verifyBMCFirmwareCheckbox)
        statusCheckLayout2.addWidget(self.verifyBIOSFirmwareCheckbox)
        statusCheckLayout2.addWidget(self.verifyFPGAFirmwareCheckbox)
        statusCheckLayout2.addWidget(self.upDownRJ45Checkbox)
        statusCheckLayout2.addWidget(self.beeperTestCheckbox)

        statusCheckLayout3 = QVBoxLayout()
        statusCheckLayout3.addWidget(self.bmcCPUCheckbox)
        statusCheckLayout3.addWidget(self.bmcFlash1Checkbox)
        statusCheckLayout3.addWidget(self.bmcFlash2Checkbox)
        statusCheckLayout3.addWidget(self.BIOSFlash1Checkbox)
        statusCheckLayout3.addWidget(self.BIOSFlash2Checkbox)

        statusCheckLayout4 = QVBoxLayout()
        statusCheckLayout4.addWidget(self.nvramCheckbox)
        statusCheckLayout4.addWidget(self.nicRJ45Checkbox)
        statusCheckLayout4.addWidget(self.phyRJ45Checkbox)
        statusCheckLayout4.addWidget(self.fpgaCheckbox)
        statusCheckLayout4.addWidget(self.poweronCheckbox)

        statusCheckLayout5 = QVBoxLayout()
        statusCheckLayout5.addWidget(self.memoryCheckbox)
        statusCheckLayout5.addWidget(self.adcCheckbox)
        statusCheckLayout5.addWidget(self.i2cCheckbox)
        statusCheckLayout5.addWidget(self.buzzerCheckbox)
        statusCheckLayout5.addWidget(self.MotherBoardLED)

        #将各个子垂直布局对象添加到主水平布局中
        statusWholeLayout.addLayout(statusCheckLayout1)
        #statusWholeLayout.addStretch(1)
        statusWholeLayout.addLayout(statusCheckLayout2)
        statusWholeLayout.addLayout(statusCheckLayout3)
        statusWholeLayout.addLayout(statusCheckLayout4)
        statusWholeLayout.addLayout(statusCheckLayout5)
        #statusWholeLayout.addStretch()

        testItemCheckGroup.setLayout(statusWholeLayout)

        #定义显示当前测试项目情况的LCD数字显示控件的布局
        LCDDisplayLayout = QHBoxLayout()
        LCDDisplayLayout.addWidget(self.CounterLCDNumber)
        LCDDisplayLayout.addWidget(self.passedLCDNumber)
        LCDDisplayLayout.addWidget(self.errorLCDNumber)
        LCDDisplayLayout.addWidget(self.hintLabel)
        LCDDisplayLayout.addStretch(1)
        counterLCDNumGroup.setLayout(LCDDisplayLayout)

        #定义当前测试进度控件的布局
        progressLayout = QHBoxLayout()
        progressLayout.addWidget(self.progressBar)
        progressGroup.setLayout(progressLayout)

        #定义串口接收到的所有Power8打印数据控件的布局
        logEditLayout = QHBoxLayout()
        logEditLayout.addWidget(self.logEdit)
        logEditGroup.setLayout(logEditLayout)

        #定义MainLayout的布局
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(serialNumGroup)
        mainLayout.addWidget(testItemCheckGroup)
        mainLayout.addWidget(counterLCDNumGroup)
        mainLayout.addWidget(progressGroup)
        mainLayout.addWidget(logEditGroup)
        #mainLayout.addStretch(1)

        self.setLayout(mainLayout)
        #开始测试button对应的connect响应函数
        startBtn.clicked.connect(self.onMsgStratBtn)

    def onMsgStratBtn(self):
        self.threader = SSHThreader(self.onMsgLogAppend)
        self.threader.start()

    @pyqtSlot(str)
    def onMsgLogAppend(self, strMsg):
        self.logEdit.append(strMsg)

#################################################################
##  BMC整机测试图形化主界面
#################################################################
class BMCChassisTestPage(QWidget):
    def __init__(self, parent=None):
        super(BMCChassisTestPage, self).__init__(parent)

        #1 定义条码录入lineedit控件
        serialNumGroup = QGroupBox("请在这里录入条码信息--------------BMC 整机测试")
        usiSNLabel = QLabel("USI条码")
        self.usiSerialNumLineEdit = QLineEdit()
        self.usiSerialNumLineEdit.setFixedWidth(240) 
        zoomSNLabel = QLabel("中太条码")
        self.zoomSerialNumLineEdit = QLineEdit()
        self.zoomSerialNumLineEdit.setFixedWidth(240) 
        macLabel = QLabel("MAC")
        self.macLineEdit = QLineEdit()
        self.macLineEdit.setFixedWidth(240) 
        startBtn = QPushButton("开始测试")
        startBtn.setFixedWidth(80)

        #2 定义状态显示控件CheckBox集合
        testItemCheckGroup = QGroupBox("各子项当前的测试状态")
        self.rtcCheckBox = QCheckBox("1-RTC测试")
        self.setMacCheckBox = QCheckBox("2-MAC设置")
        self.setZoomSNCheckBox = QCheckBox("3-ZOOM SN设置")
        self.saveLogFileCheckBox = QCheckBox("4-保存日志文件")
        self.setRTCTimeCheckBox = QCheckBox("5-设置RTC时间")

        #3定义显示当前测试项目情况的LCD数字显示控件
        counterLCDNumGroup = QGroupBox("    已测机器数    测试完成数  本次测试异常数")
        self.CounterLCDNumber = QLCDNumber()
        self.CounterLCDNumber.setDigitCount(5)
        lcdpat = self.CounterLCDNumber.palette()
        lcdpat.setColor(QPalette.Normal,QPalette.WindowText,Qt.white)
        self.CounterLCDNumber.setPalette(lcdpat)
        self.CounterLCDNumber.setSegmentStyle(QLCDNumber.Flat)
        self.CounterLCDNumber.setStyleSheet("background-color: blue")
        self.CounterLCDNumber.display('0000')

        self.passedLCDNumber = QLCDNumber()
        self.passedLCDNumber.setDigitCount(5)
        lcdpat = self.passedLCDNumber.palette()
        lcdpat.setColor(QPalette.Normal,QPalette.WindowText,Qt.white)
        self.passedLCDNumber.setPalette(lcdpat)
        self.passedLCDNumber.setSegmentStyle(QLCDNumber.Flat)
        self.passedLCDNumber.setStyleSheet("background-color: green")
        self.passedLCDNumber.display('0000')

        self.errorLCDNumber = QLCDNumber()
        self.errorLCDNumber.setDigitCount(5)
        lcdpat = self.errorLCDNumber.palette()
        lcdpat.setColor(QPalette.Normal,QPalette.WindowText,Qt.yellow)
        self.errorLCDNumber.setPalette(lcdpat)
        self.errorLCDNumber.setSegmentStyle(QLCDNumber.Flat)
        self.errorLCDNumber.setStyleSheet("background-color: red")
        self.errorLCDNumber.display('0000')
        #设置提示信息的字体，通过这个字体同时扩大了LCD显示字体的大小
        self.hintLabel=QLabel("<font color='#0000ff' size=15 background-color='#00ff00'>&nbsp;</font>")

        #定义当前测试进度控件
        progressGroup = QGroupBox("当前测试进度")
        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(100)

        #显示从串口接收到的所有Power8打印数据控件
        logEditGroup = QGroupBox("显示从串口接收到的所有Power8打印数据")
        self.logEdit = QTextEdit()
        self.logEdit.setReadOnly(True)
        self.logEdit.append("显示从串口接收到的所有Power8 Shell打印数据")
        self.logEdit.append("Log info  from the serial port of the Redpower8 ")

        #定义条码录入lineedit控件的布局
        serialNumLayout = QHBoxLayout()
        serialNumLayout.addWidget(usiSNLabel)
        serialNumLayout.addWidget(self.usiSerialNumLineEdit)
        serialNumLayout.addWidget(zoomSNLabel)
        serialNumLayout.addWidget(self.zoomSerialNumLineEdit)
        serialNumLayout.addWidget(macLabel)
        serialNumLayout.addWidget(self.macLineEdit)
        serialNumLayout.addWidget(startBtn)
        serialNumLayout.addStretch(1)
        serialNumGroup.setLayout(serialNumLayout)

        #定义Status CheckBox控件的布局, 把各个checkbox控件添加到对应的布局中, 每5个一组
        statusWholeLayout = QHBoxLayout()
        statusCheckLayout1= QVBoxLayout()
        statusCheckLayout1.addWidget(self.rtcCheckBox)
        statusCheckLayout1.addWidget(self.setMacCheckBox)
        statusCheckLayout1.addWidget(self.setZoomSNCheckBox)
        statusCheckLayout1.addWidget(self.saveLogFileCheckBox)
        statusCheckLayout1.addWidget(self.setRTCTimeCheckBox)

        #将各个子垂直布局对象添加到主水平布局中
        statusWholeLayout.addLayout(statusCheckLayout1)
        #statusWholeLayout.addStretch()

        testItemCheckGroup.setLayout(statusWholeLayout)

        #定义显示当前测试项目情况的LCD数字显示控件的布局
        LCDDisplayLayout = QHBoxLayout()
        LCDDisplayLayout.addWidget(self.CounterLCDNumber)
        LCDDisplayLayout.addWidget(self.passedLCDNumber)
        LCDDisplayLayout.addWidget(self.errorLCDNumber)
        LCDDisplayLayout.addWidget(self.hintLabel)
        LCDDisplayLayout.addStretch(1)
        counterLCDNumGroup.setLayout(LCDDisplayLayout)

        #定义当前测试进度控件的布局
        progressLayout = QHBoxLayout()
        progressLayout.addWidget(self.progressBar)
        progressGroup.setLayout(progressLayout)

        #定义串口接收到的所有Power8打印数据控件的布局
        logEditLayout = QHBoxLayout()
        logEditLayout.addWidget(self.logEdit)
        logEditGroup.setLayout(logEditLayout)

        #定义MainLayout的布局
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(serialNumGroup)
        mainLayout.addWidget(testItemCheckGroup)
        mainLayout.addWidget(counterLCDNumGroup)
        mainLayout.addWidget(progressGroup)
        mainLayout.addWidget(logEditGroup)
        #mainLayout.addStretch(1)

        self.setLayout(mainLayout)
        #开始测试button对应的connect响应函数
        startBtn.clicked.connect(self.onMsgStratBtn)

    def onMsgStratBtn(self):
        ''' 开始测试按钮的信号响应函数，用于开启BMC整机测试的SSH线程,
        同时将本界面中自定义的槽函数传递给该线程，用于和线程中的信号绑定起来 '''
        self.threader = BMCChassisSSHThreader(self.onMsgLogAppend)
        self.threader.start()

    @pyqtSlot(str)
    def onMsgLogAppend(self, strMsg):
        ''' 用于响应SSH线程发出的自定义信号，该信号在SSH线程每次接收到BMC打印数据时触发,
        本函数将SSH接收的BMC打印数据追加到日志记录控件上，每次一条 '''
        self.logEdit.append(strMsg)

###################################################
## OS的下整机测试界面
###################################################
class OSChassisTestPage(QWidget):
    def __init__(self, parent=None):
        ''' 构造函数中生成了OS下的整机测试主界面，
        具体的子控件的生成及布局可以运行程序并查看具体的显示效果 '''
        super(OSChassisTestPage, self).__init__(parent)
        #用于记录已测机器总数，测试通过机器总数，当前机器测试通过数的变量
        self.setTestedCount  = set()
        self.setPassedCount = set()
        self.currentSuccessedCount = 0

        #如下是界面上控件的定义和布局的设置
        #第一栏配置选择按钮组控件
        configGroup = QGroupBox("请在这里选择对应的机器配置--------------OS 整机测试")
        self.btn64GMem2HDD     = QPushButton("64G内存_2硬盘_整机")
        self.btn128GMem12HDD = QPushButton("128G内存_12硬盘_整机")
        self.btn256GMem12HDD = QPushButton("256G内存_12硬盘_整机")
        self.btn512GMem12HDD = QPushButton("512G内存_12硬盘_整机")
        #self.startBtn.setFixedWidth(80)

        #第二栏测试子项状态显示控件
        updateGroup = QGroupBox("各子项当前的测试状态")
        self.cpuCountCheckBox = QCheckBox("1-CPU数量测试")
        self.cpuFreqCheckBox = QCheckBox("2-CPU频率测试")
        self.cpuStressCheckBox = QCheckBox("3-CPU压力测试")
        self.memTotalCheckBox = QCheckBox("4-内存容量测试")
        self.memStreamCheckBox = QCheckBox("5-内存吞吐测试")
        self.pex8748RegCheckBox = QCheckBox("6-PEX8748寄存器测试")
        self.pex8748LinkCheckBox = QCheckBox("7-PEX8748 Link测试")
        self.marvel9230RegCheckBox = QCheckBox("8-Marvel9230寄存器测试")
        self.marvel9230LinkCheckBox = QCheckBox("9-Marvel9230 Link测试")
        self.marvel9230FuncCheckBox = QCheckBox("10-Marvel9230功能测试")
        self.bcm5718RegCheckBox = QCheckBox("11-BCM5718寄存器测试")
        self.bcm5718LinkCheckBox = QCheckBox("12-BCM5718 Link测试")
        self.ti7340RegCheckBox = QCheckBox("13-TI7340寄存器测试")
        self.ti7340LinkCheckBox = QCheckBox("14-TI7340 Link测试")
        self.ti7340FuncCheckBox = QCheckBox("15-TI7340 功能测试")
        self.intelI350RegCheckBox = QCheckBox("16-I350寄存器测试")
        self.intelI350LinkCheckBox = QCheckBox("17-I350 Link测试")
        self.intelI350FuncCheckBox = QCheckBox("18-I350 功能测试")
        self.intelI82599RegCheckBox = QCheckBox("19-I82599寄存器测试")
        self.intelI82599LinkCheckBox = QCheckBox("20-I82599 Link测试")
        self.intelI82599FuncCheckBox = QCheckBox("21-I82599 功能测试")
        self.lpcRtcCheckBox = QCheckBox("22-RTC 测试")
        self.ast2400RegCheckBox = QCheckBox("23-ast2400寄存器测试")
        self.ast2400LinkCheckBox = QCheckBox("24-ast2400 Link测试")
        self.gk107RegCheckBox = QCheckBox("25-GK107寄存器测试")
        self.gk107LinkCheckBox = QCheckBox("26-GK107 Link测试")

        progressGroup = QGroupBox("当前测试进度")
        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(100)

        #LCD number
        counterLCDNumGroup = QGroupBox("已测机器总数  测试通过机器数  本次异常数")
        self.CounterLCDNumber = QLCDNumber()
        self.CounterLCDNumber.setDigitCount(5)
        lcdpat = self.CounterLCDNumber.palette()
        lcdpat.setColor(QPalette.Normal,QPalette.WindowText,Qt.white)
        self.CounterLCDNumber.setPalette(lcdpat)

        self.CounterLCDNumber.setSegmentStyle(QLCDNumber.Flat)
        self.CounterLCDNumber.setStyleSheet("background-color: blue")
        #self.CounterLCDNumber.resize(150, 200)
        self.CounterLCDNumber.display('0000')

        self.CounterLCDNumber2 = QLCDNumber()
        self.CounterLCDNumber2.setDigitCount(5)
        lcdpat2 = self.CounterLCDNumber2.palette()
        lcdpat2.setColor(QPalette.Normal,QPalette.WindowText,Qt.white)
        self.CounterLCDNumber2.setPalette(lcdpat2)

        self.CounterLCDNumber2.setSegmentStyle(QLCDNumber.Flat)
        self.CounterLCDNumber2.setStyleSheet("background-color: green")
        #self.CounterLCDNumber2.resize(150, 200)
        self.CounterLCDNumber2.display('0000')

        self.CounterLCDNumber3 = QLCDNumber()
        self.CounterLCDNumber3.setDigitCount(5)
        lcdpat = self.CounterLCDNumber.palette()
        lcdpat.setColor(QPalette.Normal,QPalette.WindowText,Qt.yellow)
        self.CounterLCDNumber3.setPalette(lcdpat)

        self.CounterLCDNumber3.setSegmentStyle(QLCDNumber.Flat)
        self.CounterLCDNumber3.setStyleSheet("background-color: red")
        #self.CounterLCDNumber.resize(150, 200)
        self.CounterLCDNumber3.display('0000')

        self.hintLabel=QLabel("<font color='#0000ff' size=15 background-color='#00ff00'>&nbsp;</font>")

        counterLCDLayout = QHBoxLayout()
        counterLCDLayout.addWidget(self.CounterLCDNumber)
        counterLCDLayout.addWidget(self.CounterLCDNumber2)
        counterLCDLayout.addWidget(self.CounterLCDNumber3)
        counterLCDLayout.addWidget(self.hintLabel)
        counterLCDLayout.addStretch()
        counterLCDNumGroup.setLayout(counterLCDLayout)
        
        cpuLayout = QVBoxLayout()
        cpuLayout.addWidget(self.cpuCountCheckBox)
        cpuLayout.addWidget(self.cpuFreqCheckBox)
        cpuLayout.addWidget(self.cpuStressCheckBox)
        #updateGroup.setLayout(updateLayout)
        cpuLayout.addWidget(self.memTotalCheckBox)
        cpuLayout.addWidget(self.memStreamCheckBox)

        #memLayout = QVBoxLayout()
        #memLayout.addWidget(memTotalCheckBox)
        #memLayout.addWidget(memStreamCheckBox)

        pex8748Layout = QVBoxLayout()
        pex8748Layout.addWidget(self.pex8748RegCheckBox)
        pex8748Layout.addWidget(self.pex8748LinkCheckBox)

        #marvel9230Layout = QVBoxLayout()
        pex8748Layout.addWidget(self.marvel9230RegCheckBox)
        pex8748Layout.addWidget(self.marvel9230LinkCheckBox)
        pex8748Layout.addWidget(self.marvel9230FuncCheckBox)

        bcm5718Layout = QVBoxLayout()
        bcm5718Layout.addWidget(self.bcm5718RegCheckBox)
        bcm5718Layout.addWidget(self.bcm5718LinkCheckBox)

        #ti7340Layout = QVBoxLayout()
        bcm5718Layout.addWidget(self.ti7340RegCheckBox)
        bcm5718Layout.addWidget(self.ti7340LinkCheckBox)
        bcm5718Layout.addWidget(self.ti7340FuncCheckBox)

        i350Layout = QVBoxLayout()
        i350Layout.addWidget(self.intelI350RegCheckBox)
        i350Layout.addWidget(self.intelI350LinkCheckBox)
        i350Layout.addWidget(self.intelI350FuncCheckBox)
        i350Layout.addWidget(self.intelI82599RegCheckBox)
        i350Layout.addWidget(self.intelI82599LinkCheckBox)

        #i82599Layout = QVBoxLayout()
        #i82599Layout.addWidget(intelI82599RegCheckBox)
        #i82599Layout.addWidget(intelI82599LinkCheckBox)
        #i82599Layout.addWidget(intelI82599FuncCheckBox)

        lpcRtcLayout = QVBoxLayout()
        lpcRtcLayout.addWidget(self.intelI82599FuncCheckBox)
        lpcRtcLayout.addWidget(self.lpcRtcCheckBox)
        lpcRtcLayout.addWidget(self.ast2400RegCheckBox)
        lpcRtcLayout.addWidget(self.ast2400LinkCheckBox)
        lpcRtcLayout.addWidget(self.gk107RegCheckBox)
        
        gk107Layout = QVBoxLayout()
        gk107Layout.addWidget(self.gk107LinkCheckBox)

        progressLayout = QHBoxLayout()
        progressLayout.addWidget(self.progressBar)
        progressGroup.setLayout(progressLayout)

        logEditGroup = QGroupBox("显示从串口接收到的所有Power8打印数据")
        self.logEdit = QTextEdit()
        self.logEdit.setReadOnly(True)
        #logEdit.setLineWrapMode(QTextEdit.NoWrap)
        #logEdit.setPlainText("Log info 1 from Redpower8 serial port")
        self.logEdit.append("显示从串口接收到的所有Power8 Shell打印数据：")
        self.logEdit.append("Log info  from Redpower8 serial port")

        logEditLayout = QHBoxLayout()
        logEditLayout.addWidget(self.logEdit)
        logEditGroup.setLayout(logEditLayout)


        updateHLayout = QHBoxLayout()
        updateHLayout.addLayout(cpuLayout)
        #updateHLayout.addLayout(memLayout)
        updateHLayout.addLayout(pex8748Layout)
        #updateHLayout.addLayout(marvel9230Layout)
        updateHLayout.addLayout(bcm5718Layout)
        updateHLayout.addLayout(i350Layout )
        updateHLayout.addLayout(lpcRtcLayout)
        updateHLayout.addLayout(gk107Layout)
        updateGroup.setLayout(updateHLayout)

        #这里是选择机器类型的4个按钮对应的布局
        testButtonsLayout = QHBoxLayout()
        testButtonsLayout.addWidget(self.btn64GMem2HDD)
        testButtonsLayout.addWidget(self.btn128GMem12HDD)
        testButtonsLayout.addWidget(self.btn256GMem12HDD)
        testButtonsLayout.addWidget(self.btn512GMem12HDD)
        
        configLayout = QVBoxLayout()
        configLayout.addLayout(testButtonsLayout)
        configGroup.setLayout(configLayout)

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(configGroup)
        mainLayout.addWidget(updateGroup)
        mainLayout.addWidget(counterLCDNumGroup)
        mainLayout.addWidget(progressGroup)
        mainLayout.addWidget(logEditGroup)
        #mainLayout.addStretch(1)
        self.setLayout(mainLayout)

        #为64G内存配置的测试button绑定对应的消息处理函数
        self.btn64GMem2HDD.clicked.connect(self.start64GMEMBtnFunction)
        self.btn128GMem12HDD.clicked.connect(self.start64GMEMBtnFunction)
        self.btn256GMem12HDD.clicked.connect(self.start64GMEMBtnFunction)
        self.btn512GMem12HDD.clicked.connect(self.start64GMEMBtnFunction)
        

    def start64GMEMBtnFunction(self):
        ''' 按钮的消息响应函数，在这里启动一个线程，通过串口实现与P8服务器端的数据交互，
        同时会对界面上的子项测试用到的checkbox，进度条，LCD控件等做清零 '''
        #启动串口线程，同时将需要和串口类中对应的信号关联的槽函数注册进去
        print("ready to start threading module to process data received from P8")
        self.threader = OSChassisSerialPortThreader(self.onMsgAppendLog, self.onMsgUpdateStatus, self.onMsgUpdateLCDNumber)
        self.threader.start()
        #初始化进度条为0
        self.progressBar.setValue(0)

        #需要获取远端P8服务器的mac地址，这个mac地址应该由串口线程获取并通过signal方式发给GUI线程
        self.macaddress = 'OS_Chassis_Test_mac_0008d2xxxxxx'
        self.macaddress +='.log'
        self.fileWriter = fileWriter(self.macaddress)

        #用于暂时存储串口收集的信息, 最后该list中记录的P8串口输出的所有数据都会写到上面的日志文件中
        self.logList = []
        #屏蔽‘开始测试’按钮，直到测试完成后再恢复它，以免反复连续点击造成意外
        self.btn64GMem2HDD.setEnabled(False)
        self.btn128GMem12HDD.setEnabled(False)
        self.btn256GMem12HDD.setEnabled(False)
        self.btn512GMem12HDD.setEnabled(False)

        #clear checkbox status
        self.cpuCountCheckBox.setChecked(False)
        self.cpuFreqCheckBox.setChecked(False)
        self.cpuStressCheckBox.setChecked(False)
        self.memTotalCheckBox.setChecked(False)
        self.memStreamCheckBox.setChecked(False)
        self.pex8748RegCheckBox.setChecked(False)
        self.pex8748LinkCheckBox.setChecked(False)
        self.marvel9230RegCheckBox.setChecked(False)
        self.marvel9230LinkCheckBox.setChecked(False)
        self.marvel9230FuncCheckBox.setChecked(False)
        self.bcm5718RegCheckBox.setChecked(False)
        self.bcm5718LinkCheckBox.setChecked(False)
        self.ti7340RegCheckBox.setChecked(False)
        self.ti7340LinkCheckBox.setChecked(False)
        self.ti7340FuncCheckBox.setChecked(False)
        self.intelI350RegCheckBox.setChecked(False)
        self.intelI350LinkCheckBox.setChecked(False)
        self.intelI350FuncCheckBox.setChecked(False)
        self.intelI82599RegCheckBox.setChecked(False)
        self.intelI82599LinkCheckBox.setChecked(False)
        self.intelI82599FuncCheckBox.setChecked(False)
        self.lpcRtcCheckBox.setChecked(False)
        self.ast2400RegCheckBox.setChecked(False)
        self.ast2400LinkCheckBox.setChecked(False)
        self.gk107RegCheckBox.setChecked(False)
        self.gk107LinkCheckBox.setChecked(False)

        self.CounterLCDNumber3.display('0')
        self.currentSuccessedCount = 0
        self.hintLabel.setText("<font color='#0000ff' size=15 background-color='#00ff00'>&nbsp;</font>")
        #here to add more code if necessary

    @pyqtSlot(str)
    def onMsgUpdateLCDNumber(self, strmsg):
        self.CounterLCDNumber3.display(strmsg)

    @pyqtSlot(str)
    def onMsgAppendLog(self, strmsg):
        ''' 添加数据到log列表框和内存中的log数组 '''
        self.logEdit.append(strmsg)
        self.logList.append(strmsg)

    @pyqtSlot(str)
    def onMsgUpdateStatus(self, strmsg):
        if 'cpuCount' == strmsg:
            self.cpuCountCheckBox.setChecked(True)
            self.progressBar.setValue(4)
            self.currentSuccessedCount += 1
        elif 'cpuFreq' == strmsg:
            self.cpuFreqCheckBox.setChecked(True)
            self.progressBar.setValue(8)
            self.currentSuccessedCount += 1
        elif 'cpuStress' == strmsg:
            self.cpuStressCheckBox.setChecked(True)
            self.progressBar.setValue(12)
            self.currentSuccessedCount += 1
        elif 'memTotalSize' == strmsg:
            self.memTotalCheckBox.setChecked(True)
            self.progressBar.setValue(16)
            self.currentSuccessedCount += 1
        elif 'memStream' == strmsg:
            self.memStreamCheckBox.setChecked(True)
            self.progressBar.setValue(20)
            self.currentSuccessedCount += 1
        elif 'pex8748Reg' == strmsg:
            self.pex8748RegCheckBox.setChecked(True)
            self.progressBar.setValue(24)
            self.currentSuccessedCount += 1
        elif 'pex8748Link' == strmsg:
            self.pex8748LinkCheckBox.setChecked(True)
            self.progressBar.setValue(28)
            self.currentSuccessedCount += 1
        elif 'marvel9230Reg' == strmsg:
            self.marvel9230RegCheckBox.setChecked(True)
            self.progressBar.setValue(32)
            self.currentSuccessedCount += 1
        elif 'marvel9230Link' == strmsg:
            self.marvel9230LinkCheckBox.setChecked(True)
            self.progressBar.setValue(36)
            self.currentSuccessedCount += 1
        elif 'marvel9230Func' == strmsg:
            self.marvel9230FuncCheckBox.setChecked(True)
            self.progressBar.setValue(40)
            self.currentSuccessedCount += 1
        elif 'bcm5718Reg' == strmsg:
            self.bcm5718RegCheckBox.setChecked(True)
            self.progressBar.setValue(44)
            self.currentSuccessedCount += 1
        elif 'bcm5718Link' == strmsg:
            self.bcm5718LinkCheckBox.setChecked(True)
            self.progressBar.setValue(48)
            self.currentSuccessedCount += 1
        elif 'ti7340Reg' == strmsg:
            self.ti7340RegCheckBox.setChecked(True)
            self.progressBar.setValue(52)
            self.currentSuccessedCount += 1
        elif 'ti7340Link' == strmsg:
            self.ti7340LinkCheckBox.setChecked(True)
            self.progressBar.setValue(56)
            self.currentSuccessedCount += 1
        elif 'ti7340Func' == strmsg:
            self.ti7340FuncCheckBox.setChecked(True)
            self.progressBar.setValue(60)
            self.currentSuccessedCount += 1
        elif 'intelI350Reg' == strmsg:
            self.intelI350RegCheckBox.setChecked(True)
            self.progressBar.setValue(64)
            self.currentSuccessedCount += 1
        elif 'intelI350Link' == strmsg:
            self.intelI350LinkCheckBox.setChecked(True)
            self.progressBar.setValue(64)
            self.currentSuccessedCount += 1
        elif 'intelI350Func' == strmsg:
            self.intelI350FuncCheckBox.setChecked(True)
            self.progressBar.setValue(68)
            self.currentSuccessedCount += 1
        elif 'intelI82599Reg' == strmsg:
            self.intelI82599RegCheckBox.setChecked(True)
            self.progressBar.setValue(72)
            self.currentSuccessedCount += 1
        elif 'intelI82599Link' == strmsg:
            self.intelI82599LinkCheckBox.setChecked(True)
            self.progressBar.setValue(76)
            self.currentSuccessedCount += 1
        elif 'intelI82599Func' == strmsg:
            self.intelI82599FuncCheckBox.setChecked(True)
            self.progressBar.setValue(80)
            self.currentSuccessedCount += 1
        elif 'lpcRtc' == strmsg:
            self.lpcRtcCheckBox.setChecked(True)
            self.progressBar.setValue(84)
            self.currentSuccessedCount += 1
        elif 'ast2400Reg' == strmsg:
            self.ast2400RegCheckBox.setChecked(True)
            self.progressBar.setValue(88)
            self.currentSuccessedCount += 1
        elif 'ast2400Link' == strmsg:
            self.ast2400LinkCheckBox.setChecked(True)
            self.progressBar.setValue(92)
            self.currentSuccessedCount += 1
        elif 'gk107Reg' == strmsg:
            self.gk107RegCheckBox.setChecked(True)
            self.progressBar.setValue(96)
            self.currentSuccessedCount += 1
        elif 'gk107Link' == strmsg:
            self.gk107LinkCheckBox.setChecked(True)
            self.progressBar.setValue(100)
            self.currentSuccessedCount += 1
        elif 'END' == strmsg:
            self.progressBar.setValue(100)
            #最后写日志文件
            self.fileWriter.writeFullLogFile(self.logList)
            self.fileWriter.close()
            #恢复‘开始测试’按钮
            self.startBtn.setEnabled(True)
            #根据测试结果更新LCD显示控件上的统计数字
            snUSI = self.serialNumEdit.text()
            errorsCount = 26-self.currentSuccessedCount
            if 0 == errorsCount:
                #testing successed, 把测试的机器的条码信息记录到对应set集合中
                self.setTestedCount.add(snUSI)
                self.setPassedCount.add(snUSI)
                self.CounterLCDNumber.display(str(len(self.setTestedCount)))
                self.CounterLCDNumber2.display(str(len(self.setPassedCount)))
                self.CounterLCDNumber3.display("0")
                #self.hintLabel.setText("<font color='#0000ff' size=15>TEST PASSED</font>")
            else:
                #testing failed, 设置测试的统计信息到LCD显示控件上，测试通过数不添加到set中
                self.setTestedCount.add(snUSI)
                self.CounterLCDNumber.display(str(len(self.setTestedCount)))
                self.CounterLCDNumber2.display(str(len(self.setPassedCount)))
                self.CounterLCDNumber3.display(str(errorsCount))
                #self.hintLabel.setText("<font color='#ff0000' size=15>TEST FAILED</font>")
                QMessageBox.information(self, "OS Chassis 整机测试", "错误：测试失败",  QMessageBox.Yes)
        else:
            pass


####################################################################
 


class UpdatePage(QWidget):
    def __init__(self, parent=None):
        super(UpdatePage, self).__init__(parent)

        updateGroup = QGroupBox("Package selection")
        systemCheckBox = QCheckBox("BIOS Package")
        appsCheckBox = QCheckBox("BMC Package")
        docsCheckBox = QCheckBox("FPGA Package")

        packageGroup = QGroupBox("Existing packages")

        packageList = QListWidget()
        qtItem = QListWidgetItem(packageList)
        qtItem.setText("test item 1")
        qsaItem = QListWidgetItem(packageList)
        qsaItem.setText("test item 2")
        teamBuilderItem = QListWidgetItem(packageList)
        teamBuilderItem.setText("test item 3")

        startUpdateButton = QPushButton("Start update")

        updateLayout = QVBoxLayout()
        updateLayout.addWidget(systemCheckBox)
        updateLayout.addWidget(appsCheckBox)
        updateLayout.addWidget(docsCheckBox)
        updateGroup.setLayout(updateLayout)

        packageLayout = QVBoxLayout()
        packageLayout.addWidget(packageList)
        packageGroup.setLayout(packageLayout)

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(updateGroup)
        mainLayout.addWidget(packageGroup)
        mainLayout.addSpacing(12)
        mainLayout.addWidget(startUpdateButton)
        mainLayout.addStretch(1)

        self.setLayout(mainLayout)



class QueryPage(QWidget):
    def __init__(self, parent=None):
        super(QueryPage, self).__init__(parent)

        packagesGroup = QGroupBox("Look for packages")

        nameLabel = QLabel("Name:")
        nameEdit = QLineEdit()

        dateLabel = QLabel("Released after:")
        dateEdit = QDateTimeEdit(QDate.currentDate())

        releasesCheckBox = QCheckBox("Releases")
        upgradesCheckBox = QCheckBox("Upgrades")

        hitsSpinBox = QSpinBox()
        hitsSpinBox.setPrefix("Return up to ")
        hitsSpinBox.setSuffix(" results")
        hitsSpinBox.setSpecialValueText("Return only the first result")
        hitsSpinBox.setMinimum(1)
        hitsSpinBox.setMaximum(100)
        hitsSpinBox.setSingleStep(10)

        startQueryButton = QPushButton("Start query")

        packagesLayout = QGridLayout()
        packagesLayout.addWidget(nameLabel, 0, 0)
        packagesLayout.addWidget(nameEdit, 0, 1)
        packagesLayout.addWidget(dateLabel, 1, 0)
        packagesLayout.addWidget(dateEdit, 1, 1)
        packagesLayout.addWidget(releasesCheckBox, 2, 0)
        packagesLayout.addWidget(upgradesCheckBox, 3, 0)
        packagesLayout.addWidget(hitsSpinBox, 4, 0, 1, 2)
        packagesGroup.setLayout(packagesLayout)

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(packagesGroup)
        mainLayout.addSpacing(12)
        mainLayout.addWidget(startQueryButton)
        mainLayout.addStretch(1)

        self.setLayout(mainLayout)


class ConfigDialog(QDialog):

    def __init__(self, parent=None):
        super(ConfigDialog, self).__init__(parent)

        self.contentsWidget = QListWidget()
        self.contentsWidget.setViewMode(QListView.IconMode)
        #self.contentsWidget.setIconSize(QSize(96, 84))
        self.contentsWidget.setIconSize(QSize(56, 52))
        self.contentsWidget.setMovement(QListView.Static)
        #self.contentsWidget.setMaximumWidth(80)
        self.contentsWidget.setMaximumWidth(200)
        self.contentsWidget.setSpacing(15)
		
        self.pagesWidget = QStackedWidget()
        self.pagesWidget.addWidget(BIOSPCBAPage())
        self.pagesWidget.addWidget(BMCChassisTestPage())
        self.pagesWidget.addWidget(BmcPcbaPage())
        self.pagesWidget.addWidget(OSChassisTestPage())
        self.pagesWidget.addWidget(QueryPage())
        self.pagesWidget.addWidget(BIOSPCBAPage())

        self.pagesWidget.addWidget(BIOSPCBAPage())
        self.pagesWidget.addWidget(UpdatePage())
        self.pagesWidget.addWidget(BmcPcbaPage())
        self.pagesWidget.addWidget(UpdatePage())
        self.pagesWidget.addWidget(QueryPage())
        self.pagesWidget.addWidget(BIOSPCBAPage())

        self.pagesWidget.addWidget(BIOSPCBAPage())
        self.pagesWidget.addWidget(UpdatePage())
        self.pagesWidget.addWidget(BmcPcbaPage())
        self.pagesWidget.addWidget(UpdatePage())
        self.pagesWidget.addWidget(QueryPage())

        closeButton = QPushButton("Close")

        #为list控件添加子元素，即带图标的列表子控件
        self.createIcons()
        self.contentsWidget.setCurrentRow(0)

        closeButton.clicked.connect(self.close)
		
        horizontalLayout = QHBoxLayout()
        horizontalLayout.addWidget(self.contentsWidget)
        horizontalLayout.addWidget(self.pagesWidget, 1)

        logEditLayout = QHBoxLayout()
        #logEditLayout.addStretch()
        #logEditLayout.addWidget(self.logEdit)
		
        buttonsLayout = QHBoxLayout()
        buttonsLayout.addStretch(1)
        buttonsLayout.addWidget(closeButton)

        mainLayout = QVBoxLayout()
        mainLayout.addLayout(horizontalLayout)
        #mainLayout.addStretch(1)
        mainLayout.addSpacing(12)
        #mainLayout.addLayout(logEditLayout)
        mainLayout.addLayout(buttonsLayout)

        self.setLayout(mainLayout)

        self.setWindowTitle("生产测试程序v1.0-无锡中太服务器有限公司 ZOOM Co., Ltd.")

    def appendLogEdit(self,strbuf):
        self.logEdit.append(strbuf)

    def changePage(self, current, previous):
        if not current:
            current = previous

        self.pagesWidget.setCurrentIndex(self.contentsWidget.row(current))

    def createIcons(self):
        configButton = QListWidgetItem(self.contentsWidget)
        configButton.setIcon(QIcon(':/images/config.png'))
        configButton.setText("设置")
        configButton.setTextAlignment(Qt.AlignHCenter)
        configButton.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

        pcbaButton = QListWidgetItem(self.contentsWidget)
        pcbaButton.setIcon(QIcon(':/images/update.png'))
        pcbaButton.setText("FPGA升级")
        pcbaButton.setTextAlignment(Qt.AlignHCenter)
        pcbaButton.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

        bmcButton = QListWidgetItem(self.contentsWidget)
        bmcButton.setIcon(QIcon(':/images/update.png'))
        bmcButton.setText("BMC")
        bmcButton.setTextAlignment(Qt.AlignHCenter)
        bmcButton.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

        fanButton = QListWidgetItem(self.contentsWidget)
        fanButton.setIcon(QIcon(':/images/config.png'))
        fanButton.setText("风扇")
        fanButton.setTextAlignment(Qt.AlignHCenter)
        fanButton.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

        rj45Button = QListWidgetItem(self.contentsWidget)
        rj45Button.setIcon(QIcon(':/images/update.png'))
        rj45Button.setText("RJ45网卡")
        rj45Button.setTextAlignment(Qt.AlignHCenter)
        rj45Button.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

        fpgaButton = QListWidgetItem(self.contentsWidget)
        fpgaButton.setIcon(QIcon(':/images/update.png'))
        fpgaButton.setText("主板")
        fpgaButton.setTextAlignment(Qt.AlignHCenter)
        fpgaButton.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

        osButton = QListWidgetItem(self.contentsWidget)
        osButton.setIcon(QIcon(':/images/update.png'))
        osButton.setText("整机")
        osButton.setTextAlignment(Qt.AlignHCenter)
        osButton.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

        memButton = QListWidgetItem(self.contentsWidget)
        memButton.setIcon(QIcon(':/images/config.png'))
        memButton.setText("内存")
        memButton.setTextAlignment(Qt.AlignHCenter)
        memButton.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

        fblButton = QListWidgetItem(self.contentsWidget)
        fblButton.setIcon(QIcon(':/images/config.png'))
        fblButton.setText("FBL面板")
        fblButton.setTextAlignment(Qt.AlignHCenter)
        fblButton.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
		
        biosButton = QListWidgetItem(self.contentsWidget)
        biosButton.setIcon(QIcon(':/images/config.png'))
        biosButton.setText("BIOS升级")
        biosButton.setTextAlignment(Qt.AlignHCenter)
        biosButton.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

        bmcupgradeButton = QListWidgetItem(self.contentsWidget)
        bmcupgradeButton.setIcon(QIcon(':/images/config.png'))
        bmcupgradeButton.setText("BMC升级")
        bmcupgradeButton.setTextAlignment(Qt.AlignHCenter)
        bmcupgradeButton.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

        macButton = QListWidgetItem(self.contentsWidget)
        macButton.setIcon(QIcon(':/images/config.png'))
        macButton.setText("烧录MAC")
        macButton.setTextAlignment(Qt.AlignHCenter)
        macButton.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

        powerOnButton = QListWidgetItem(self.contentsWidget)
        powerOnButton.setIcon(QIcon(':/images/config.png'))
        powerOnButton.setText("开机测试")
        powerOnButton.setTextAlignment(Qt.AlignHCenter)
        powerOnButton.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

        powerOffButton = QListWidgetItem(self.contentsWidget)
        powerOffButton.setIcon(QIcon(':/images/config.png'))
        powerOffButton.setText("关机测试")
        powerOffButton.setTextAlignment(Qt.AlignHCenter)
        powerOffButton.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

        hddPanelButton = QListWidgetItem(self.contentsWidget)
        hddPanelButton.setIcon(QIcon(':/images/config.png'))
        hddPanelButton.setText("硬盘背板")
        hddPanelButton.setTextAlignment(Qt.AlignHCenter)
        hddPanelButton.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

        self.contentsWidget.currentItemChanged.connect(self.changePage)
        #self.contentsWidget2.currentItemChanged.connect(self.changePage2)
        #self.contentsWidget3.currentItemChanged.connect(self.changePage3)

class BiosPCBAProcess(object):
    def process(self):
        print("ready to enter the BIOS Shell")
        ser = SerialPort('/dev/ttyUSB0', 115200, 1)

        while True:
            string = ser.readline()
            print(string)
            #ConfigDialog.appendLogEdit(string)
            if len(string)>0:
                print(string)
                if 'Welcome to Petitboot' in string:
                    print('login BIOS Shell now \n')
                    ser.writeBytes(b'\r')
                    break

        ser.close()
        print("login to bios shell now")


if __name__ == '__main__':
    import sys

    app = QApplication(sys.argv)
    dialog = ConfigDialog()
    dialog.resize(1400,1000)
    sys.exit(dialog.exec_())    
