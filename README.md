# uartLog

usage: uartLog.py [-h] [-n N]

Uart analysis program.

optional arguments:
  -h, --help  show this help message and exit
  -n N        log name

While program running, it's able to change running state with some command:
1. ":a" command to show all logs without filter
2. ":r xxx1\&xxx2" command to get all logs which contains "xxx1" or "xxx2"
