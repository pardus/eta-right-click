import sys

from util import send_ev

from evdev import ecodes as e

"""
EV_ABS ABS_X 0
EV_ABS ABS_Y 0
EV_SYN SYN_REPORT 0
EV_KEY BTN_RIGHT 1
EV_SYN SYN_REPORT 0
EV_KEY BTN_RIGHT 0
EV_SYN SYN_REPORT 0
"""

if len(sys.argv) > 2:
    i=1
    while i < len(sys.argv):
        print(i, sys.argv[i])
        if sys.argv[i] == "click":
            send_ev("EV_KEY", sys.argv[i+1], 1)
            send_ev("EV_SYN", "SYN_REPORT", 0)
            send_ev("EV_KEY", sys.argv[i+1], 0)
            send_ev("EV_SYN", "SYN_REPORT", 0)
            i += 2
            continue
        if sys.argv[i] == "move":
            send_ev("EV_ABS", "ABS_X", int(sys.argv[i+1]))
            send_ev("EV_ABS", "ABS_Y", int(sys.argv[i+1]))
            send_ev("EV_SYN", "SYN_REPORT", 0)
            i += 3
            continue
    sys.exit(0)

while True:
    try:
        line = input().strip().split(" ")
        if len(line) > 2:
            print(line)
            send_ev(line[0], line[1], int(line[2]))
    except (EOFError, KeyboardInterrupt):
        break
