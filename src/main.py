#!/usr/bin/env python3
import fcntl, os
import math
import time
from util import *
import configparser
import subprocess

import random
import traceback
import socket
import struct
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

event_hold="right-click"
event_release=""
event_tap=""


try:
    config = configparser.ConfigParser()
    config.read("/etc/pardus/eta-right-click.conf")
    timeout   = float(config["main"]["timeout"])
    threshold  = float(config["main"]["threshold"])
    event_hold  = str(config["event"]["hold"])
    event_release  = str(config["event"]["release"])
    event_tap  = str(config["event"]["tap"])
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
        self.ui = None
        self.abs_max = [dev.absinfo(e.ABS_X).max, dev.absinfo(e.ABS_Y).max]
        self.pos_begin = [-1, -1]
        self.pos = [-1,-1]
        self.cur_event = []
        self.saved_events = []
        self.exit_handler = None
        self.lock = False
        self.num_of_touch = 0
        self.ev_time = time.time()
        self.id = 0

    def send_ev(self, etype, ecode, evalue):
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect("/run/eta-click.sock")
            sock.sendall(struct.pack('iii', etype, ecode, evalue))
            sock.close()
        except Exception as e:
            log(f"eta-click socket error: {e}")


    def do_event_config(self, conf):
        print(conf)
        if conf == "ignore":
            return
        elif conf == "right-click":
            self.do_click(e.BTN_RIGHT)
        elif conf.startswith("exec::"):
            threading.Thread(target=subprocess.run, args=(["sh", "-c", conf[6:]],)).start()

    def reset_handler(self):
        cap = self.dev.capabilities()
        del cap[0]
        cap[e.EV_KEY] += [e.BTN_RIGHT, e.BTN_LEFT]
        if self.ui:
            self.dev.ungrab()
            self.ui.close()
            del self.ui
        self.ui = UInput(cap, name=f"Amogus device ({self.dev.name})", vendor=0x31, product=0x31)
        self.dev.grab()

    @asynchronous
    def do_click(self, btn):
        if self.pos[0] < 0 or self.pos[1] < 0:
            return
        x = int((3840*self.pos[0]) / self.abs_max[0])
        y = int((2160*self.pos[1]) / self.abs_max[1])
        delay = random.random()*0.02 + 0.02
        self.send_ev(e.EV_ABS, e.ABS_X, x)
        self.send_ev(e.EV_ABS, e.ABS_Y, y)
        self.send_ev(0, 0, 0)

        self.send_ev(e.EV_KEY, btn, 1)
        self.send_ev(0, 0, 0)
        time.sleep(delay)
        self.send_ev(e.EV_KEY, btn, 0)
        self.send_ev(0, 0, 0)

    def release_click_handler(self):
        print('event::release')
        self.do_event_config(event_release)

    def right_click_handler(self, id):
        if self.id != id:
            return
        if check_disable():
            return
        self.lock = True
        print('event::hold')
        self.do_event_config(event_hold)


    def tap_handler(self):
        print("event::tap")
        self.do_event()
        delay = random.random()*0.02 + 0.02
        time.sleep(delay)
        self.do_event_config(event_tap)


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

    def is_multi_touch(self, evs):
        count = 0
        slot_detect = False
        for ev in evs:
            if (ev.type == e.EV_ABS and ev.code == e.ABS_MT_SLOT):
                slot_detect = True
                break
            if (ev.type == e.EV_ABS and ev.code == e.ABS_MT_TRACKING_ID):
                if ev.value > 0:
                    count += 1
                else:
                    count -= 1
        return count > 1 or slot_detect

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

    def calculate_touch(self):
        if self.is_pressed(self.cur_event):
            self.num_of_touch += 1
        elif self.is_released(self.cur_event):
            self.num_of_touch -= 1

    def do_event(self):
        for _evs in self.saved_events:
            for _ev in _evs:
                self.ui.write_event(_ev)
            self.ui.syn()
        self.saved_events = []

    def event_action(self, ev):
        if ev and ev.type != e.EV_SYN:
            print_event(ev)
            self.cur_event.append(ev)
            return False

        self.get_event_pos()

        distance = self.calculate_distance()
        self.calculate_touch()

        if len(self.cur_event) == 0:
            return False
        if self.is_multi_touch(self.cur_event) or self.num_of_touch > 1:
            self.saved_events.append(self.cur_event)
            self.do_event()
            self.cur_event = []
            self.id += 1
            return False
        elif self.is_pressed(self.cur_event):
            print("press", self.pos, self.pos_begin, self.num_of_touch)
            self.pos_begin[0] = self.pos[0]
            self.pos_begin[1] = self.pos[1]
            self.ev_time = time.time()
            self.saved_events.append(self.cur_event)
            self.id += 1
            GLib.timeout_add(timeout, self.right_click_handler, self.id)
        elif self.is_released(self.cur_event):
            print("release", self.pos, self.pos_begin, distance, self.num_of_touch)
            if self.lock:
                self.saved_events = []
                self.cur_event = []
                self.lock = False
                self.release_click_handler()
                if time.time() - self.ev_time > 10:
                    print("reset")
                    self.reset_handler()
                return False
            if distance < threshold:
                self.tap_handler()
            self.pos_begin = [-1, -1]
            self.id += 1
        elif self.is_move(self.cur_event):
            print("move", self.pos, self.pos_begin, distance, self.num_of_touch)
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

        self.saved_events.append(self.cur_event)
        self.do_event()
        self.cur_event = []
        print("====================")


    @asynchronous
    def listen(self):
        self.reset_handler()
        if event_hold == "ignore" and event_release == "ignore" and event_tap == "ignore":
            for ev in self.dev.read_loop():
                self.ui.write_event(ev)

        # Bu kısımda eventler okunur
        try:
            ev_old = None
            for ev in self.dev.read_loop():
                # üst üste 2 kere syn gelmemesi için
                if ev_old == e.EV_SYN and ev.type == e.EV_SYN:
                    continue
                ev_old = ev.type
                if ev.type == e.EV_ABS and ev.code == e.ABS_MT_TRACKING_ID:
                    self.event_action(None)
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
