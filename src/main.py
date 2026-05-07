#!/usr/bin/env python3
import fcntl, os
import math
import time
from util import *
import configparser

import traceback
import subprocess
import threading

from gi.repository import GLib
from evdev import UInput, InputDevice, AbsInfo, ecodes as e
from evdev.evtest import print_event

from netlink import NetlinkSocket
import sys

log=print
if "--debug" not in sys.argv:
    def print(*args, **kwargs):
        pass

timeout   = 500  # uzun basma bekleme süresi
threshold = 20 # görmezden gelinen minimum pixel


try:
    config = configparser.ConfigParser()
    config.read("/etc/pardus/eta-right-click.conf")
    timeout   = float(config["main"]["timeout"])
    threshold  = float(config["main"]["threshold"])
except Exception as err:
    log(err)


runtime_dir = "/run/etap/right-click"
os.makedirs(f"{runtime_dir}/disable", exist_ok=True)
os.chmod(f"{runtime_dir}/disable", 0o1777)

def check_disable():
    if not os.path.isdir(f"{runtime_dir}/disable"):
        print("enable: runtime missing")
        return False
    disabled = False
    for pid in os.listdir(f"{runtime_dir}/disable"):
        if os.path.isdir(f"/proc/{pid}"):
            print("disable: block by "+ pid)
            disabled = True
        else:
            os.unlink(f"{runtime_dir}/disable/{pid}")
    return disabled

class Device:

    def __init__(self, dev):
        self.dev = dev
        self.abs_max = [dev.absinfo(e.ABS_X).max, dev.absinfo(e.ABS_Y).max]
        self.pos_begin = [-1, -1]
        self.pos = [-1,-1]
        self.cur_event = []
        self.saved_events = []
        self.exit_handler = None
        self.lock = False
        self.id = 0

    @asynchronous
    def do_click(self, btn):
        if self.pos[0] < 0 or self.pos[1] < 0:
            return
        x = int((3840*self.pos[0]) / self.abs_max[0])
        y = int((2160*self.pos[1]) / self.abs_max[1])
        subprocess.run(["eta-click", btn, str(x), str(y)])

    def right_click_handler(self, id):
        if self.id != id:
            return
        if check_disable():
            return
        self.lock = True
        self.do_click("right")
        print('check-click')

    def is_pressed(self, evs):
        for ev in evs:
            if (ev.type == e.EV_KEY and (ev.code == e.BTN_LEFT or ev.code == e.BTN_TOUCH) and ev.value == 1) \
                or (ev.type == e.EV_ABS and ev.code == e.ABS_MT_TRACKING_ID and ev.value != -1):
                return True
        return False

    def get_event_pos(self):
        for ev in self.cur_event:
            if (ev.code == e.BTN_LEFT or ev.code == e.BTN_TOUCH):
                self.pos[0] = self.dev.absinfo(e.ABS_X).value
                self.pos[1] = self.dev.absinfo(e.ABS_Y).value
            if ev.code == e.ABS_MT_POSITION_X:
                self.pos[0] = ev.value
            if ev.code == e.ABS_MT_POSITION_Y:
                self.pos[1] = ev.value

    def is_released(self, evs):
        for ev in evs:
            if (ev.type == e.EV_KEY and (ev.code == e.BTN_LEFT or ev.code == e.BTN_TOUCH) and ev.value == 0) \
                    or (ev.type == e.EV_ABS and ev.code == e.ABS_MT_TRACKING_ID and ev.value == -1):
                return True
        return False

    def is_move(self, evs):
        for ev in evs:
            if ev.type == e.EV_ABS and (ev.code == e.ABS_X or ev.code == e.ABS_Y \
                or ev.code == e.ABS_MT_POSITION_X or ev.code == e.ABS_MT_POSITION_Y):
                    return True
        return False


    def calculate_distance(self):
        a = abs(self.pos[0] - self.pos_begin[0])
        a = (a*3840) /self.abs_max[0]
        b = abs(self.pos[1] - self.pos_begin[1])
        b = (b*2160) /self.abs_max[1]
        return int(math.sqrt(a**2 + b**2))

    def do_event(self):
        print("do-event")
        for _evs in self.saved_events:
            for _ev in _evs:
                self.ui.write_event(_ev)
            self.ui.syn()
        self.saved_events = []

    def event_action(self, ev):
        #print_event(ev)
        self.ev = ev

        if ev.type != e.EV_SYN:
            self.cur_event.append(ev)
            return False

        self.get_event_pos()

        distance = self.calculate_distance()
        if len(self.cur_event) == 0:
            return False
        elif self.is_pressed(self.cur_event):
            self.pos_begin[0] = self.pos[0]
            self.pos_begin[1] = self.pos[1]
            print("press", self.pos, self.pos_begin)
            self.saved_events.append(self.cur_event)
            self.id += 1
            GLib.timeout_add(timeout, self.right_click_handler, self.id)
        elif self.is_released(self.cur_event):
            print("release", self.pos, self.pos_begin, distance)
            if self.lock:
                self.saved_events = []
                self.cur_event = []
                self.lock = False
                self.pos = [-1, -1]
                return False
            if distance < threshold:
                self.do_event()
            self.pos_begin = [-1, -1]
            self.pos = [-1, -1]
            self.id += 1
        elif self.is_move(self.cur_event):
            print("move", self.pos, self.pos_begin, distance)
            if distance > threshold:
                self.id += 1
                self.do_event()
            else:
                self.saved_events.append(self.cur_event)
        else:
            print("other", self.pos, self.pos_begin)


        if len(self.saved_events) > 0:
            self.cur_event = []
            return False

        for _ev in self.cur_event:
            self.ui.write_event(_ev)
        self.ui.write_event(ev)
        self.cur_event = []


    @asynchronous
    def listen(self):
        cap = self.dev.capabilities()
        del cap[0]
        cap[e.EV_KEY] += [e.BTN_RIGHT, e.BTN_LEFT]
        self.ui = UInput(cap, name=f"Amogus device ({self.dev.name})", vendor=0x31, product=0x31)
        self.dev.grab()

        # Bu kısımda eventler okunur
        try:
            ev_old = None
            for ev in self.dev.read_loop():
                # üst üste 2 kere syn gelmemesi için
                if ev_old == e.EV_SYN and ev.type == e.EV_SYN:
                    continue
                ev_old = ev.type
                if ev.type in [e.EV_MSC]:
                    self.ui.write_event(ev)
                elif self.event_action(ev):
                    pass
        except:
            print("Device event read failed {}".format(traceback.format_exc()))
            if self.exit_handler:
                GLib.idle_add(self.exit_handler, self)


devices = []

def exit_handler(d):
    if d.fd_path in devices:
        devices.remove(d.fd_path)
    print("Device removed {}".format(d.fd_path))
    del(d)

def check_device(f):
    # event olmayanları es geç
    if not f.startswith("event"):
        return
    fd = "/dev/input/" +f
    if fd in devices:
        return
    print("Available:", f)
    devices.append(fd)
    # device classı oluştur ve ekle
    dev = InputDevice(fd)
    cap = dev.capabilities()
    if "Amogus" in dev.name:
        return
    # burda uygun olup olmama kontrolü yapılır
    if (e.EV_KEY in cap and e.BTN_TOUCH in cap[e.EV_KEY]) \
        or (e.EV_ABS in cap and (e.ABS_X in cap[e.EV_ABS] or e.ABS_MT_POSITION_X in cap[e.EV_ABS])):
        if e.BTN_TOOL_FINGER in cap[e.EV_KEY] or \
           e.BTN_TOOL_DOUBLETAP in cap[e.EV_KEY] or \
           e.BTN_TOOL_TRIPLETAP in cap[e.EV_KEY]:
            return
        print("Track:", f, dev.name)
        d = Device(dev)
        d.fd_path = fd
        d.exit_handler = exit_handler
        d.listen()

def nls_action(event):
    if "ACTION" in event:
        if event["ACTION"] != "add":
            return
    if "DEVNAME" not in event:
        return
    if not event["DEVNAME"].startswith("/dev/input/"):
        return

    check_device(event["DEVNAME"].split("/")[-1])
    print("====")
    print(event)

def scan_devices():
    # Device listesi oluşturmak için dizini taradık
    for f in os.listdir("/dev/input"):
        check_device(f)
    nls = NetlinkSocket()
    nls.action = nls_action
    th = threading.Thread(target=nls.run)
    th.start()

GLib.idle_add(scan_devices)
# glib loopu kapanmayı engeller ve timeout_add çalışmasını sağlar.
main = GLib.MainLoop()
main.run()
