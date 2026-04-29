#!/usr/bin/env python3
import fcntl, os
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
        self.move_count = 0
        self.evtime = 0
        self.pos = [-1,-1]
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


    def is_pressed(self, ev):
        return ((ev.code == e.BTN_LEFT or ev.code == e.BTN_TOUCH) and ev.value == 1) \
                or (ev.code == e.ABS_MT_TRACKING_ID and ev.value != -1)

    def get_event_pos(self, ev):
        if (ev.code == e.BTN_LEFT or ev.code == e.BTN_TOUCH):
            self.pos[0] = self.dev.absinfo(e.ABS_X).value
            self.pos[1] = self.dev.absinfo(e.ABS_Y).value
        if ev.code == e.ABS_MT_POSITION_X:
            self.pos[0] = ev.value
        if ev.code == e.ABS_MT_POSITION_Y:
            self.pos[1] = ev.value

    def is_released(self, ev):
        released =  ((ev.code == e.BTN_LEFT or ev.code == e.BTN_TOUCH) and ev.value == 0) \
                or (ev.code == e.ABS_MT_TRACKING_ID and ev.value == -1)
        if released:
            self.pos = [-1, -1]
        return released


    def is_move(self, ev):
        return (ev.code == e.ABS_X or ev.code == e.ABS_Y) \
                or (ev.code == e.ABS_MT_POSITION_X or ev.code == e.ABS_MT_POSITION_Y)

    def event_action(self, ev):
        self.ev = ev

        self.get_event_pos(ev)

        print_event(ev)

        # event kabul etme
        if self.is_pressed(ev):
            print("press", self.pos)
        if self.is_released(ev):
            print("release", self.pos)
        if self.is_move(ev):
            print("move", self.pos)
        return True

    @asynchronous
    def listen(self):
        cap = self.dev.capabilities()
        del cap[0]
        cap[e.EV_KEY] += [e.BTN_RIGHT, e.BTN_LEFT]
        self.ui = UInput(cap, name=f"Amogus device ({self.dev.name})", vendor=0x31, product=0x31)
        self.dev.grab()

        # Bu kısımda eventler okunur
        try:
            for ev in self.dev.read_loop():
                if ev.type in [e.EV_MSC, e.EV_SYN]:
                    self.ui.write_event(ev)
                elif self.event_action(ev) or check_disable():
                    self.ui.write_event(ev)
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
