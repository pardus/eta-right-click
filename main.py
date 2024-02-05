import fcntl, os, libevdev
import time
from util import *

from gi.repository import GLib

from evdev import UInput, ecodes as e

sensitive = 1.5

capabilities = {
    e.EV_KEY : (e.BTN_LEFT, e.BTN_RIGHT),
}

ui = UInput(capabilities)

devices = []
for f in os.listdir("/dev/input"):
    fd = open("/dev/input/event2", "rb")
    dev = libevdev.Device(fd)
    if dev.has(libevdev.EV_KEY.BTN_LEFT):
        devices.append(dev)
        break

block = False
ctime = time.time()
left_click_lock = False

def handle_right_click():
    global left_click_lock
    if not block:
        if time.time() - ctime < sensitive:
            return
        left_click_lock = True

def do_left_click():
    global left_click_lock
    ui.write(e.EV_KEY, e.BTN_RIGHT, 1)
    ui.syn()
    time.sleep(sensitive / 10)
    ui.write(e.EV_KEY, e.BTN_RIGHT, 0)
    ui.syn()
    left_click_lock = False


@asynchronous
def listen_device(dev):
    global block, ctime
    for e in dev.events():
        ctime = time.time()
        if e.matches(libevdev.EV_KEY.BTN_LEFT):
            if e.value == 1:
                block = False
                GLib.timeout_add(sensitive*1000,handle_right_click)
            else:
                block = True
                if left_click_lock:
                    do_left_click()
        if e.matches(libevdev.EV_ABS):
            block = True

for dev in devices:
    listen_device(dev)

main = GLib.MainLoop()
main.run()