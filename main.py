#!/usr/bin/env
import fcntl, os
import time
from util import *
import configparser

from gi.repository import GLib
from evdev import UInput, InputDevice, ecodes as e
import sys

log=print
if "--debug" not in sys.argv:
    def print(*args, **kwargs):
        pass

sensitive = 0.1  # cihaza göre ayarlanması gereken hassaslık
timeout   = 700  # uzun basma bekleme süresi
treshold  = 0.05 # görmezden gelinen minimum oran

config = configparser.ConfigParser()
config.read("/etc/pardus/eta-right-click.conf")

try:
    sensitive = float(config["main"]["sensitive"])
    timeout   = float(config["main"]["timeout"])
    treshold  = float(config["main"]["treshold"])
except Exception as err:
    log(err)
    sys.exit(1)

capabilities = {
    e.EV_KEY : (e.BTN_LEFT, e.BTN_RIGHT),
}

ui = UInput(capabilities)


# sağ tık yap
def do_right_click():
    time.sleep(0.3)
    ui.write(e.EV_KEY, e.BTN_RIGHT, 1)
    ui.syn()
    time.sleep(0.3)
    ui.write(e.EV_KEY, e.BTN_RIGHT, 0)
    ui.syn()
    print('click')


class Device:

    def __init__(self, dev):
        self.dev = dev
        self.pressed = False
        self.num_of_touch = 0
        self.move_count = 0
        self.value = 0
        self.cur_x = dev.absinfo(e.ABS_X).value
        self.cur_y = dev.absinfo(e.ABS_Y).value
        self.ctime = time.time()
        self.btime = time.time()
        self.left_click_lock = False
        self.block = False

    def dump(self, action="dump"):
        print("========== {} ==========".format(time.time()))
        print("Action:", action)
        print("EV:", self.ev.code)
        print("Pressed:", self.pressed)
        print("Num of Touch:", self.num_of_touch)
        print("Move count:", self.move_count)
        print("X cursor:", self.cur_x)
        print("Y cursor:", self.cur_y)
        print("Current time:", self.ctime)
        print("Button time:", self.btime)
        print("Lock:", self.left_click_lock)
        print("Block:", self.block)


    def do_left_click_event(self):
        self.ctime = time.time()
        self.btime = time.time()
        self.cur_x = self.dev.absinfo(e.ABS_X).value
        self.cur_y = self.dev.absinfo(e.ABS_Y).value
        # zamana bak ve sağ tık yapılacak mı karar ver
        def handle_right_click():
            if self.pressed and not self.block:
                self.left_click_lock = True
                self.dump("lock")
            elif self.left_click_lock:
                do_right_click()
                self.left_click_lock = False
                self.dump("right-click")
        if self.ev.value == 1:
            # birden çok basma eventini engelle
            if self.pressed:
                return
            # uzun basma kadar süreden sonra çalıştırmak için
            self.pressed = True
            self.dump("press")
            GLib.timeout_add(timeout,handle_right_click)
        else:
            self.pressed = False
            self.block = False
            self.dump("release")
            # kilitlendiyse ve engellenmediyse sağ tıkla
            handle_right_click()


    def do_cancel_event(self, is_x, value):
        if self.block or self.left_click_lock:
            return
        # basma zamanının 100ms kadarlık süresine kadarki hareket eventleri görmezden gelinir.
        if time.time() - self.btime < sensitive:
            self.dump("ignore-time")
            return
        # kaydırma miktarını ölç ve yetersizse görmezden gel
        if is_x == None:
            # zorla engellemek için
            ratio = 1
            diff = 0
        elif is_x:
            diff = abs(value - self.cur_x)
            ratio = diff / self.dev.absinfo(e.ABS_X).max
        else:
            diff = abs(value - self.cur_y)
            ratio = diff / self.dev.absinfo(e.ABS_Y).max
        if ratio < treshold:
            self.dump("ignore-treshold")
            return
        self.dump("cancel")
        print("Ratio:", ratio)
        print("Diff:", diff)
        print(self.ev.value , self.cur_y, self.cur_x)
        self.ctime = time.time()
        self.block = True


    @asynchronous
    def listen(self):
        # Bu kısımda eventler okunur
        for ev in dev.read_loop():
            self.ev = ev
            if not os.path.exists(self.dev.fd):
                print("Wait for enable")
                time.sleep(5)
                continue
            # multi touch parmak sayma
            if ev.code == e.ABS_MT_TRACKING_ID:
                if ev.value == -1:
                    self.num_of_touch -= 1
                else:
                    self.num_of_touch += 1

            # hareket ettirilirse sağ tuş eventi iptal edilmeli
            if ev.code == e.ABS_X or ev.code == e.ABS_Y:
                self.do_cancel_event(ev.code == e.ABS_X, self.dev.absinfo(ev.code).value)
            # multi touch hareket eventi
            elif ev.code == e.ABS_MT_POSITION_X or ev.code == e.ABS_MT_POSITION_Y:
                if self.num_of_touch == 1:
                     self.move_count += 1
                self.do_cancel_event(ev.code == e.ABS_MT_POSITION_X, ev.value)

            # tuşa basma eventi kontrolü
            if ev.code == e.BTN_LEFT or ev.code == e.BTN_TOUCH:
                self.do_left_click_event()
            # multi touch eventi kontrolü
            elif ev.code == e.ABS_MT_TRACKING_ID:
                if self.num_of_touch == 0:
                    self.ev.value = 0
                    self.move_count = 0
                    self.do_left_click_event()
                elif self.num_of_touch == 1:
                    self.ev.value = 1
                    self.do_left_click_event()
                else:
                    self.do_cancel_event(None, -1 )


# Device listesi oluşturmak için dizini taradık
for f in os.listdir("/dev/input"):
    # event olmayanları es geç
    if not f.startswith("event"):
        print("Available:", f)
        continue
    # device classı oluştur ve ekle
    fd = "/dev/input/" +f
    dev = InputDevice(fd)
    cap = dev.capabilities()
    # burda uygun olup olmama kontrolü yapılır
    print(cap)
    if (e.EV_KEY in cap and e.BTN_TOUCH in cap[e.EV_KEY]) \
        or (e.EV_ABS in cap and (e.ABS_X in cap[e.EV_ABS] or e.ABS_MT_POSITION_X in cap[e.EV_ABS])):
        print("Track:", f)
        d = Device(dev)
        d.listen()

# glib loopu kapanmayı engeller ve timeout_add çalışmasını sağlar.
main = GLib.MainLoop()
main.run()
