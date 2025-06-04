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

devices = []
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
        devices.append(dev)
    else:
        print("ignore", f)

# global değişkenler
block = False # basma eventi engellendi mi
ctime = time.time() # en son event zamanı
btime = time.time() # tuşa basma zamanı
left_click_lock = False # sağ tık eventi gelsin mi


# zamana bak ve sağ tık yapılacak mı karar ver
def handle_right_click():
    global left_click_lock, block
    if pressed and not block:
        print("lock", time.time() - ctime)
        left_click_lock = True

# sağ tık yap
def do_left_click():
    global left_click_lock
    time.sleep(0.3)
    ui.write(e.EV_KEY, e.BTN_RIGHT, 1)
    ui.syn()
    time.sleep(0.3)
    ui.write(e.EV_KEY, e.BTN_RIGHT, 0)
    ui.syn()
    print('click')
    left_click_lock = False



num_of_touch = 0
move_count = 0
cur_x = 0
cur_y = 0

pressed = False
def do_left_click_event(ev):
    global block, ctime, btime, num_of_touch, pressed, cur_x, cur_y
    ctime = time.time()
    btime = time.time()
    cur_x = dev.absinfo(e.ABS_X).value
    cur_y = dev.absinfo(e.ABS_Y).value
    if ev.value == 1:
        # birden çok basma eventini engelle
        if pressed:
            return
        # uzun basma kadar süreden sonra çalıştırmak için
        pressed = True
        print("press", btime, move_count, ev, left_click_lock, block)
        GLib.timeout_add(timeout,handle_right_click)
    else:
        pressed = False
        block = False
        print("release", btime, move_count, ev, left_click_lock, block)
        if left_click_lock and not block:
            do_left_click()

def do_cancel_event(dev, ev, is_x):
    global block, ctime, btime, num_of_touch, move_count
    # basma zamanının 100ms kadarlık süresine kadarki hareket eventleri görmezden gelinir.
    if time.time() - btime < sensitive:
        print("ignore-time", sensitive - (time.time() - btime))
        return
    # kaydırma miktarını ölç ve yetersizse görmezden gel
    if is_x == None:
        # zorla engellemek için
        ratio = 1
        diff = 0
    elif is_x:
        diff = abs(dev.absinfo(e.ABS_X).value - cur_x)
        ratio = diff / dev.absinfo(e.ABS_X).max
    else:
        diff = abs(dev.absinfo(e.ABS_Y).value - cur_y)
        ratio = diff / dev.absinfo(e.ABS_Y).max
    if ratio < treshold:
        print("ignore-diff", diff, ratio)
        return
    print("cancel", btime, move_count, diff, ratio)
    ctime = time.time()
    block = True


@asynchronous
def listen_device(dev):
    global block, ctime, btime, num_of_touch, move_count
    # Bu kısımda eventler okunur
    for ev in dev.read_loop():
        print("event:", ev,
              "device:", dev.fd,
              "press:", pressed,
              "block:", block,
              "lock:", left_click_lock,
              "touch:", num_of_touch,
              "count:", move_count,
              "abs_cur_x:", dev.absinfo(e.ABS_X).value,
              "abs_cur_y:", dev.absinfo(e.ABS_Y).value
        )
        if not os.path.exists(dev.fd):
            print("Wait for enable")
            time.sleep(5)
            continue
        # multi touch parmak sayma
        if ev.code == e.ABS_MT_TRACKING_ID:
            if ev.value == -1:
                num_of_touch -= 1
            else:
                num_of_touch += 1

        # hareket ettirilirse sağ tuş eventi iptal edilmeli
        if ev.code == e.ABS_X or ev.code == e.ABS_Y:
            do_cancel_event(dev, ev, ev.code == e.ABS_X)
        # multi touch hareket eventi
        elif ev.code == e.ABS_MT_POSITION_X or ev.code == e.ABS_MT_POSITION_Y:
            if num_of_touch == 1:
                move_count += 1
            do_cancel_event(dev, ev, ev.code == e.ABS_MT_POSITION_X)

        # tuşa basma eventi kontrolü
        if ev.code == e.BTN_LEFT or ev.code == e.BTN_TOUCH:
            do_left_click_event(ev)
        # multi touch eventi kontrolü
        elif ev.code == e.ABS_MT_TRACKING_ID:
            if num_of_touch == 0:
                ev.value = 0
                move_count = 0
                do_left_click_event(ev)
            elif num_of_touch == 1:
                ev.value = 1
                do_left_click_event(ev)
            else:
                do_cancel_event(dev, ev, None)

# dinlemeye başla
for dev in devices:
    print(dev.absinfo)
    listen_device(dev)
# glib loopu kapanmayı engeller ve timeout_add çalışmasını sağlar.
main = GLib.MainLoop()
main.run()
