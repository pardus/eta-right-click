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
# Device listesi oluşturmak için dizini taradık
for f in os.listdir("/dev/input"):
    # event olmayanları es geç
    if not f.startswith("event"):
        print(f)
        continue
    # device classı oluştur ve ekle
    fd = open("/dev/input/" +f, "rb")
    dev = libevdev.Device(fd)
    # burda uygun olup olmama kontrolü yapılır
    if True or dev.has(libevdev.EV_KEY.BTN_LEFT):
        devices.append(dev)
    else:
        print(dev)

# global değişkenler
block = False # basma eventi engellendi mi
ctime = time.time() # en son event zamanı
btime = time.time() # tuşa basma zamanı
left_click_lock = False # sağ tık eventi gelsin mi


# zamana bak ve sağ tık yapılacak mı karar ver
def handle_right_click():
    global left_click_lock
    if not block:
        print(time.time() - ctime , sensitive * 1000)
        if time.time() - ctime < sensitive:
            return
        left_click_lock = True
        print(block, left_click_lock)

# sağ tık yap
def do_left_click():
    global left_click_lock
    time.sleep(0.3)
    ui.write(e.EV_KEY, e.BTN_RIGHT, 1)
    ui.syn()
    time.sleep(sensitive / 10)
    ui.write(e.EV_KEY, e.BTN_RIGHT, 0)
    ui.syn()
    print('click')
    left_click_lock = False


@asynchronous
def listen_device(dev):
    global block, ctime, btime
    # Bu kısımda eventler okunur
    for e in dev.events():
        # tuşa basma eventi kontrolü
        if e.matches(libevdev.EV_KEY.BTN_LEFT) or e.matches(libevdev.EV_KEY.BTN_TOUCH):
            ctime = time.time()
            print(e, left_click_lock, block)
            btime = time.time()
            if e.value == 1:
                block = False
                # sassaslık kadar süreden sonra çalıştırmak için
                GLib.timeout_add(sensitive*1000,handle_right_click)
            else:
                if left_click_lock:
                    do_left_click()

        if left_click_lock:
            continue
        # hareket ettirilirse sağ tuş eventi iptal edilmeli
        if e.matches(libevdev.EV_ABS.ABS_X) or e.matches(libevdev.EV_ABS.ABS_Y):
            # basma zamanının 100ms kadarlık süresine kadarki hareket eventleri görmezden gelinir.
            if time.time() - btime < 100:
                continue
            print(e)
            ctime = time.time()
            block = True


# dinlemeye başla
for dev in devices:
    listen_device(dev)
# glib loopu kapanmayı engeller ve timeout_add çalışmasını sağlar.
main = GLib.MainLoop()
main.run()
