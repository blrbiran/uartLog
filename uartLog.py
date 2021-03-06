#!/usr/bin/env python
# coding: utf-8
import serial
import argparse

import threading

import sys
import os
import re
import time

# Global Settings
reStr = r""
port = "COM6"
baud = 115200 * 8
FLAG_OUTPUT_FILTER_FILE = False
fullLogTime = 5

# reference: https://github.com/pyserial/pyserial/issues/216
class ReadLine:
    def __init__(self, s):
        self.buf = bytearray()
        self.s = s

    def readline(self):
        i = self.buf.find(b"\n")
        if i >= 0:
            r = self.buf[:i+1]
            self.buf = self.buf[i+1:]
            return r
        while True:
            i = max(1, min(2048, self.s.in_waiting))
            data = self.s.read(i)
            i = data.find(b"\n")
            if i >= 0:
                r = self.buf + data[:i+1]
                self.buf[0:] = data[i+1:]
                return r
            else:
                self.buf.extend(data)

# get regex results
def getFilter(logStr, reStr):
    reFilter = re.compile(reStr, re.I + re.M + re.U)
    result = reFilter.findall(logStr)
    if [] == result:
        return ""
    else:
        return result

# filter uart data then print to stdout and write to files
def handleData(line, reStr=r"^.*()+.*$", fileHandler=None, filterFileHandler=None):
    try:
        newLine = line.decode().strip()
        if fileHandler:
            fileHandler.write(newLine + "\n")
        ret = getFilter(newLine, reStr)
        if "" != ret:
            print(newLine)
            if filterFileHandler:
                filterFileHandler.write(newLine + "\n")
    except UnicodeDecodeError as e:
        print(e)
        print(line)

# single thread for read uart data
def readFromPort(serial, fileHandler=None, filterFileHandler=None):
    global reStr

    serialReadLine = ReadLine(serial)
    while True:
        line = serialReadLine.readline()   # read a '\n' terminated line
        # line = serial.readline()
        handleData(line, reStr, fileHandler, filterFileHandler)

# get escaped key words for regex
def escapeKeyword(keyList):
    escapeKeyList = [ re.escape(key) for key in keyList ]
    return escapeKeyList

# handle program control command
def handleSettingCmd(command, serial, fileHandler, filterFileHandler=None):
    global reStr
    global fullLogTime
    global FLAG_OUTPUT_FILTER_FILE

    print("Cmd:" + command)
    if command[0] == 'a':
        # print all log
        reStr = r"^.*()+.*$"
    elif command[0] == 'r':
        escapedFilterKeyList = escapeKeyword(command[2:].split("\&"))
        reStr = r"^.*(" + r"|".join(escapedFilterKeyList) + r")+.*$"
        print("reStr: " + reStr)
    elif command[0] == 't':
        try:
            fullLogTime = int(command[2:].strip())
            print("Show full log time: %ds" % fullLogTime)
        except ValueError:
            fullLogTime = 5
            print("Show full log time: default 5s")
    elif command[0] == 'q':
        print("Byebye!")
        if FLAG_OUTPUT_FILTER_FILE:
            filterFileHandler.close()
        fileHandler.close()
        # serial.close()
        os._exit(0)

# reset reStr variable after timeout seconds
def setReStrAfter(newReStr=r"^.*()+.*$",timeout=fullLogTime):
    global reStr
    showLogEvent = threading.Event()
    showLogEvent.wait(timeout=fullLogTime)
    reStr = newReStr

# handle user command
def handleCmd(serial, command, fileHandler, filterFileHandler=None):
    global reStr

    if command == "":
        cmd = "\n".encode("gbk")
        serial.write(cmd)
        serial.flushOutput()
    elif command[0] == ':':
        handleSettingCmd(command[1:], serial, fileHandler, filterFileHandler)
    else:
        tmpReStr = reStr
        reStr = r"^.*()+.*$"
        cmd = command + "\n"
        cmd = cmd.encode("gbk")
        # write to file
        fileHandler.write(command + "\n")
        if filterFileHandler:
            filterFileHandler.write(command + "\n")
        # write to serial
        serial.write(cmd)
        serial.flushOutput()
        delayedWork = threading.Thread(target=setReStrAfter,args=(tmpReStr, fullLogTime))
        delayedWork.start()

def sendCtrlC(serial):
    global reStr
    tmpReStr = reStr
    reStr = r"^.*()+.*$"
    # Ctrl-C => 0x03
    cmd = chr(0x03).encode("gbk")
    serial.write(cmd)
    serial.flushOutput()
    delayedWork = threading.Thread(target=setReStrAfter,args=(tmpReStr, fullLogTime))
    delayedWork.start()

def main(args):
    global reStr
    global port
    global baud
    global FLAG_OUTPUT_FILTER_FILE

    # Setting Here
    port = "COM6"
    baud = 115200 * 8
    filterKeyList = ["rtc", "usb"]

    # filterKeyList = [""]
    escapedFilterKeyList = escapeKeyword(filterKeyList)
    reStr = r"^.*(" + r"|".join(escapedFilterKeyList) + r")+.*$"
    print("reStr: " + reStr)

    # parser parameter
    if args.n == None:
        filenamePrefix = "out"
    elif args.n[0] != "":
        filenamePrefix = args.n[0]
    else:
        filenamePrefix = "out"

    if args.f == False:
        FLAG_OUTPUT_FILTER_FILE = False
    else:
        FLAG_OUTPUT_FILTER_FILE = True

    filenameTimestamp = time.strftime("%Y%m%d_%H%M%S")
    filenameSuffix = ".log"
    filename = filenamePrefix + "_" + filenameTimestamp + filenameSuffix
    filterFilename = filenamePrefix + "_" + filenameTimestamp + "-filter" + filenameSuffix

    ser = serial.Serial(port, baud, timeout=None)
    ser.close()
    ser.open()

    f = open(filename, "w")
    if FLAG_OUTPUT_FILTER_FILE:
        filterf = open(filterFilename, "w")
    else:
        filterf = None

    # start reading thread
    readThread = threading.Thread(target=readFromPort, args=(ser, f, filterf))
    readThread.start()

    # wait for input from command line
    while True:
        try:
            command = input()
            handleCmd(ser, command, f, filterf)
        except KeyboardInterrupt:
            # send Ctrl-C to console
            sendCtrlC(ser)
            # continue

    if FLAG_OUTPUT_FILTER_FILE:
        filterf.close()
    f.close()
    ser.close()

# parser arguments
def parseArg():
    parser = argparse.ArgumentParser(description='Uart analysis program.')
    parser.add_argument('-n', nargs=1, help='log name')
    parser.add_argument('-f', help='export filter file', action="store_true")
    args = parser.parse_args()
    print(args)
    return args

if __name__ == '__main__':
    # ref: https://docs.python.org/2/library/sys.html#sys.setcheckinterval
    # set thread switches interval
    sys.setcheckinterval = 20
    args = parseArg()
    main(args)

