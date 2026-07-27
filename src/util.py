import threading

from gi.repository import GLib

import struct
import socket

from evdev import ecodes as e

def asynchronous(func):
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.daemon = True
        thread.start()
        return thread
    return wrapper

def idle(func):
    def wrapper(*args, **kwargs):
        GLib.idle_add(func, *args, **kwargs)
    return wrapper



sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect("/run/eta-click.sock")

def send_ev(etype, ecode, evalue):
    try:
        if etype in e.ecodes:
            etype = e.ecodes[etype]
        if ecode in e.ecodes:
            ecode = e.ecodes[ecode]
        sock.sendall(struct.pack('iii', int(etype), int(ecode), int(evalue)))
    except Exception as exc:
        print(f"eta-click socket error: {exc}")
