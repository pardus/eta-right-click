import fcntl, os, libevdev
import time
from util import *

from gi.repository import GLib

from evdev import UInput, ecodes as e

sensitive = 0.7

capabilities = {
    e.EV_KEY : (e.BTN_LEFT, e.BTN_RIGHT),
}

ui = UInput(capabilities)

devices = []
for f in os.listdir("/dev/input"):
    if not f.startswith("event"):
        print(f)
        continue
    fd = open("/dev/input/" +f, "rb")
    dev = libevdev.Device(fd)
    if True or dev.has(libevdev.EV_KEY.BTN_LEFT):
        devices.append(dev)
        
    else:
        print(dev)

block = False
ctime = time.time()
btime = time.time()
left_click_lock = False

def handle_right_click():
    global left_click_lock
    if not block:
        print(time.time() - ctime , sensitive * 1000)
        if time.time() - ctime < sensitive:
            return
        left_click_lock = True
        print(block, left_click_lock)
    
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
    global block, ctime, btime
    for e in dev.events():
        if e.matches(libevdev.EV_KEY.BTN_LEFT) or e.matches(libevdev.EV_KEY.BTN_TOUCH):
            ctime = time.time()
            print(e)
            btime = time.time()
            if e.value == 1:
                block = False
                GLib.timeout_add(sensitive*1000,handle_right_click)
            else:
                block = True
                if left_click_lock:
                    do_left_click()

        print(e,time.time() - btime, time.time() - ctime)
        if e.matches(libevdev.EV_ABS.ABS_X) or e.matches(libevdev.EV_ABS.ABS_Y):
            if time.time() - btime < 100:
                continue
            print(e)
            ctime = time.time()
            block = True

for dev in devices:
    listen_device(dev)

main = GLib.MainLoop()
main.run()
