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
# Device listesi oluşturmak için dizini taradık
for f in os.listdir("/dev/input"):
    # event olmayanları es geç
    if not f.startswith("event"):
        print("Available:", f)
        continue
    # device classı oluştur ve ekle
    fd = open("/dev/input/" +f, "rb")
    dev = libevdev.Device(fd)
    # burda uygun olup olmama kontrolü yapılır
    if dev.has(libevdev.EV_KEY.BTN_TOUCH) or dev.has(libevdev.EV_ABS.ABS_X) or dev.has(libevdev.EV_ABS.ABS_MT_POSITION_X):
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
    global left_click_lock
    if not block:
        print(time.time() - ctime , sensitive * 1000)
        if time.time() - ctime < sensitive:
            return
        left_click_lock = True
        print("lock")

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



num_of_touch = 0
move_count = 0

def do_left_click_event(e):
    global block, ctime, btime, num_of_touch
    print("left-click", btime, move_count)
    ctime = time.time()
    print(e, left_click_lock, block)
    btime = time.time()
    if e.value == 1:
        # sassaslık kadar süreden sonra çalıştırmak için
        GLib.timeout_add(sensitive*1000,handle_right_click)
    else:
        if left_click_lock:
            do_left_click()

def do_cancel_event(e):
    global block, ctime, btime, num_of_touch, move_count
    # basma zamanının 100ms kadarlık süresine kadarki hareket eventleri görmezden gelinir.
    print("cancel", btime, move_count)
    if time.time() - btime < sensitive:
        return True
    ctime = time.time()
    block = True
    return True

@asynchronous
def listen_device(dev):
    global block, ctime, btime, num_of_touch, move_count
    # Bu kısımda eventler okunur
    for e in dev.events():
        print("diff", time.time() - btime, e, dev.fd.name)
        if not os.path.exists(dev.fd.name):
            print("Wait for enable")
            time.sleep(5)
            continue
        if e.matches(libevdev.EV_ABS.ABS_MT_TRACKING_ID):
            if e.value == -1:
                num_of_touch -= 1
            else:
                num_of_touch += 1
            ev = e
            if num_of_touch == 0:
                ev.value = 0
                move_count = 0
                do_left_click_event(ev)
            elif num_of_touch == 1:
                ev.value = 1
                do_left_click_event(ev)
            else:
                if do_cancel_event(e):
                    continue
        # tuşa basma eventi kontrolü
        elif e.matches(libevdev.EV_KEY.BTN_LEFT) or e.matches(libevdev.EV_KEY.BTN_TOUCH):
            do_left_click_event(e)
        if left_click_lock:
            continue
        # multi touch hareket eventi
        if e.matches(libevdev.EV_ABS.ABS_MT_POSITION_X):
            print("touch:",num_of_touch, "count:", move_count)
            if num_of_touch == 1:
                move_count += 1
            if do_cancel_event(e):
                continue
        # hareket ettirilirse sağ tuş eventi iptal edilmeli
        elif e.matches(libevdev.EV_ABS.ABS_X) or e.matches(libevdev.EV_ABS.ABS_Y):
            if do_cancel_event(e):
                continue

# dinlemeye başla
for dev in devices:
    listen_device(dev)
# glib loopu kapanmayı engeller ve timeout_add çalışmasını sağlar.
main = GLib.MainLoop()
main.run()
