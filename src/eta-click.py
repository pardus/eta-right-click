import struct
import socket

from evdev import ecodes as e



def send_ev(etype, ecode, evalue):
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect("/run/eta-click.sock")
        sock.sendall(struct.pack('iii', etype, ecode, evalue))
        sock.close()
    except Exception as exc:
        print(f"eta-click socket error: {exc}")

"""
EV_ABS ABS_X 0
EV_ABS ABS_Y 0
EV_SYN SYN_REPORT 0
EV_KEY BTN_RIGHT 1
EV_SYN SYN_REPORT 0
EV_KEY BTN_RIGHT 0
EV_SYN SYN_REPORT 0
"""

if __name__ == "__main__":
    while True:
        try:
            line = input().strip().split(" ")
            print(line)
            send_ev(e.ecodes[line[0]], e.ecodes[line[1]], int(line[2]))
        except (EOFError, KeyboardInterrupt):
            break
