#!/usr/bin/env python3
import configparser
import math
import os
import random
import socket
import struct
import subprocess
import sys
import threading
import time
import traceback

from gi.repository import GLib
from evdev import UInput, InputDevice, ecodes as e

from netlink import NetlinkSocket
from util import asynchronous, send_ev

if "--debug" not in sys.argv:
    def debug_log(*_args, **_kwargs):
        pass
    def print_event(*_args, **_kwargs):
        pass
else:
    from evdev.evtest import print_event
    debug_log = print

TIMEOUT = 500
THRESHOLD = 20

EVENT_HOLD = "right-click"
EVENT_RELEASE = "ignore"
EVENT_TAP = "ignore"
DELAY_MODE = False

try:
    config = configparser.ConfigParser()
    config.read("/etc/pardus/eta-right-click.conf")
    TIMEOUT = float(config["main"]["timeout"])
    DELAY_MODE = str(config["main"]["delaymode"]).lower() == "true"
    THRESHOLD = float(config["main"]["threshold"])
    EVENT_HOLD = str(config["event"]["hold"])
    EVENT_RELEASE = str(config["event"]["release"])
    EVENT_TAP = str(config["event"]["tap"])
except Exception as err:
    debug_log(err)


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
        self.fd_path = None
        self.abs_max = [dev.absinfo(e.ABS_X).max, dev.absinfo(e.ABS_Y).max]
        self.pos_begin = [-1, -1]
        self.pos = [-1, -1]
        self.cur_event = []
        self.saved_events = []
        self.exit_handler = None
        self.lock = False
        self.num_of_touch = 0
        self.ev_time = time.time()
        self.event_id = 0

    def do_event_config(self, conf):
        debug_log(conf)
        if conf == "ignore":
            return True
        if conf == "right-click":
            self.do_click(e.BTN_RIGHT)
        elif conf == "left-click":
            self.do_click(e.BTN_LEFT)
        elif conf.startswith("exec::"):
            threading.Thread(target=subprocess.run, args=(["sh", "-c", conf[6:]],)).start()
        return False

    def reset_handler(self):
        cap = self.dev.capabilities()
        del cap[0]
        cap[e.EV_KEY] += [e.BTN_RIGHT, e.BTN_LEFT]
        if self.ui:
            self.dev.ungrab()
            self.ui.close()
            del self.ui
        self.ui = UInput(
            cap,
            name=f"Amogus device ({self.dev.name})",
            phys="",
            vendor=0x31,
            product=0x31,
        )
        self.dev.grab()

    @asynchronous
    def do_click(self, btn):
        if self.pos[0] < 0 or self.pos[1] < 0:
            return
        x = int((3840*self.pos[0]) / self.abs_max[0])
        y = int((2160*self.pos[1]) / self.abs_max[1])
        delay = random.random()*0.02 + 0.02
        send_ev(e.EV_ABS, e.ABS_X, x)
        send_ev(e.EV_ABS, e.ABS_Y, y)
        send_ev(0, 0, 0)

        send_ev(e.EV_KEY, btn, 1)
        send_ev(0, 0, 0)
        time.sleep(delay)
        send_ev(e.EV_KEY, btn, 0)
        send_ev(0, 0, 0)

    def release_click_handler(self):
        debug_log('event::release')
        self.do_event_config(EVENT_RELEASE)

    def right_click_handler(self, eid):
        if self.event_id != eid:
            return
        if check_disable():
            return
        self.lock = True
        debug_log('event::hold')
        self.do_event_config(EVENT_HOLD)


    def tap_handler(self):
        debug_log("event::tap")
        if self.do_event_config(EVENT_TAP):
            self.do_event('tap')


    def is_pressed(self, evs):
        for ev in evs:
            if ev.type == e.EV_ABS and ev.code == e.ABS_MT_TRACKING_ID and ev.value != -1:
                return True
            if ev.type == e.EV_KEY and ev.value == 1 and ev.code in (e.BTN_LEFT, e.BTN_TOUCH):
                return True
        return False

    def get_event_pos(self):
        for ev in self.cur_event:
            if ev.code in (e.BTN_LEFT, e.BTN_TOUCH):
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
            if ev.type == e.EV_ABS and ev.code == e.ABS_MT_TRACKING_ID and ev.value == -1:
                return True
            if ev.type == e.EV_KEY and ev.value == 0 and ev.code in (e.BTN_LEFT, e.BTN_TOUCH):
                return True
        return False

    def is_move(self, evs):
        for ev in evs:
            if ev.type == e.EV_ABS and ev.code in (
                e.ABS_X, e.ABS_Y, e.ABS_MT_POSITION_X, e.ABS_MT_POSITION_Y,
            ):
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

    def do_event(self, name=''):
        t = 0
        for _evs, _time in self.saved_events:
            if DELAY_MODE:
                if t > 0:
                    time.sleep(_time - t)
                t = _time
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
            self.saved_events.append((self.cur_event, time.time()))
            self.do_event('multi-touch')
            self.cur_event = []
            self.event_id += 1
            return False
        if self.is_pressed(self.cur_event):
            debug_log("press", self.pos, self.pos_begin, self.num_of_touch)
            self.pos_begin[0] = self.pos[0]
            self.pos_begin[1] = self.pos[1]
            self.ev_time = time.time()
            self.saved_events.append((self.cur_event, time.time()))
            self.event_id += 1
            GLib.timeout_add(TIMEOUT, self.right_click_handler, self.event_id)
        elif self.is_released(self.cur_event):
            debug_log("release", self.pos, self.pos_begin, distance, self.num_of_touch)
            if self.lock:
                self.saved_events = []
                self.cur_event = []
                self.lock = False
                self.release_click_handler()
                if time.time() - self.ev_time > 10:
                    debug_log("reset")
                    self.reset_handler()
                return False
            if distance < THRESHOLD:
                self.saved_events.append((self.cur_event, time.time()))
                self.tap_handler()
            self.pos_begin = [-1, -1]
            self.event_id += 1
        elif self.is_move(self.cur_event):
            debug_log("move", self.pos, self.pos_begin, distance, self.num_of_touch)
            if distance > THRESHOLD:
                self.event_id += 1
                self.do_event('move')
            else:
                self.saved_events.append((self.cur_event, time.time()))
        else:
            debug_log("other", self.pos, self.pos_begin)


        if len(self.saved_events) > 0:
            self.cur_event = []
            return False

        self.saved_events.append((self.cur_event, time.time()))
        self.do_event('other')
        self.cur_event = []
        debug_log("====================")


    @asynchronous
    def listen(self):
        self.reset_handler()

        try:
            if EVENT_HOLD == "ignore" and EVENT_RELEASE == "ignore" and EVENT_TAP == "ignore":
                for ev in self.dev.read_loop():
                    self.ui.write_event(ev)
            else:
                ev_old = None
                for ev in self.dev.read_loop():
                    if ev_old == e.EV_SYN and ev.type == e.EV_SYN:
                        continue
                    ev_old = ev.type
                    if ev.type == e.EV_ABS and ev.code == e.ABS_MT_TRACKING_ID:
                        self.event_action(None)
                    if ev.type in [e.EV_MSC]:
                        self.ui.write_event(ev)
                    elif self.event_action(ev):
                        pass
        except Exception:
            debug_log(f"Device event read failed {traceback.format_exc()}")
            self.ui.close()
            del self.ui
            if self.exit_handler:
                GLib.idle_add(self.exit_handler, self)


devices = []

def exit_handler(dev):
    if dev.fd_path in devices:
        devices.remove(dev.fd_path)
    debug_log(f"Device removed {dev.fd_path}")
    del dev

def check_device(name):
    if not name.startswith("event"):
        return
    fd = "/dev/input/" + name
    if fd in devices:
        return
    debug_log("Available:", name)
    devices.append(fd)
    dev = InputDevice(fd)
    cap = dev.capabilities()
    if "Amogus" in dev.name:
        return
    touch_key = e.EV_KEY in cap and e.BTN_TOUCH in cap[e.EV_KEY]
    touch_abs = (
        e.EV_ABS in cap
        and (e.ABS_X in cap[e.EV_ABS] or e.ABS_MT_POSITION_X in cap[e.EV_ABS])
    )
    if touch_key or touch_abs:
        if (
            e.BTN_TOOL_FINGER in cap[e.EV_KEY]
            or e.BTN_TOOL_DOUBLETAP in cap[e.EV_KEY]
            or e.BTN_TOOL_TRIPLETAP in cap[e.EV_KEY]
        ):
            return
        debug_log("Track:", name, dev.name)
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
    debug_log("====")
    debug_log(event)

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
