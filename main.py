#!/usr/bin/env python3
import fcntl, os
import math
import time
from util import *
import configparser

import traceback
import threading

from gi.repository import GLib
from evdev import UInput, InputDevice, ecodes as e
from evdev.evtest import print_event

from netlink import NetlinkSocket
import sys

log=print
if "--debug" not in sys.argv:
    def print(*args, **kwargs):
        pass

sensitive = 0.1  # cihaza göre ayarlanması gereken hassaslık
timeout   = 700  # uzun basma bekleme süresi
threshold = 0.05 # görmezden gelinen minimum oran

config = configparser.ConfigParser()
config.read("/etc/pardus/eta-right-click.conf")

try:
    sensitive = float(config["main"]["sensitive"])
    timeout   = float(config["main"]["timeout"])
    threshold  = float(config["main"]["threshold"])
except Exception as err:
    log(err)
    sys.exit(1)


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
        self.move_count = 0
        self.evtime = 0
        self.pos_begin = [-1, -1]
        self.pos = [-1,-1]
        self.cur_event = []
        self.lock = False
        self.saved_events = []
        self.exit_handler = None


    # sağ tık yap
    def do_right_click(self):
        time.sleep(0.3)
        self.ui.write(e.EV_KEY, e.BTN_RIGHT, 1)
        self.ui.syn()
        time.sleep(0.3)
        self.ui.write(e.EV_KEY, e.BTN_RIGHT, 0)
        self.ui.syn()
        print('click')

    # düz tık yap
    def do_left_click(self):
        self.ui.write(e.EV_KEY, e.BTN_TOUCH, 1)
        self.ui.syn()
        #time.sleep(0.3)
        self.ui.write(e.EV_KEY, e.BTN_TOUCH, 0)
        self.ui.syn()
        print('touch click')


    def is_pressed(self):
        for ev in self.cur_event:
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
        self.pos[0] = (1920*self.pos[0]) / self.abs_max[0]
        self.pos[1] = (1080*self.pos[1]) / self.abs_max[1]

    def is_released(self):
        for ev in self.cur_event:
            if (ev.type == e.EV_KEY and (ev.code == e.BTN_LEFT or ev.code == e.BTN_TOUCH) and ev.value == 0) \
                    or (ev.type == e.EV_ABS and ev.code == e.ABS_MT_TRACKING_ID and ev.value == -1):
                self.pos = [-1, -1]
                return True
        return False

    def is_move(self):
        for ev in self.cur_event:
            if ev.type == e.EV_ABS and (ev.code == e.ABS_X or ev.code == e.ABS_Y \
                or ev.code == e.ABS_MT_POSITION_X or ev.code == e.ABS_MT_POSITION_Y):
                    return True
        return False


    def calculate_distance(self):
        a = abs(self.pos[0] - self.pos_begin[0])
        a = (a*1920) /self.abs_max[0]
        b = abs(self.pos[1] - self.pos_begin[1])
        b = (b*1080) /self.abs_max[1]
        return math.sqrt(a**2 + b**2)

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
        elif self.is_pressed():
            self.pos_begin[0] = self.pos[0]
            self.pos_begin[1] = self.pos[1]
            print("press", self.pos, self.pos_begin)
            self.saved_events.append(self.cur_event)
        elif self.is_released():
            self.pos_begin = [-1, -1]
            print("release", self.pos, self.pos_begin, distance)
            if distance < threshold:
                self.do_event()
        elif self.is_move():
            print("move", self.pos, self.pos_begin, distance)
            if distance > threshold:
                self.do_event()
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
                elif self.event_action(ev) or check_disable():
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
