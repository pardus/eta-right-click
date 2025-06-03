import fcntl, os, libevdev
import time
from util import *

from gi.repository import GLib

from evdev import UInput, ecodes as e

sensitive = 0.1 # cihaza göre ayarlanması gereken hassaslık
timeout = 700 # uzun basma bekleme süresi

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

abs_max_x = -1
abs_max_y = -1

abs_cur_x = -1
abs_cur_y = -1

pressed = False
def do_left_click_event(e):
    global block, ctime, btime, num_of_touch, pressed, abs_cur
    ctime = time.time()
    btime = time.time()
    if e.value == 1 and not pressed:
        # uzun basma kadar süreden sonra çalıştırmak için
        pressed = True
        print("press", btime, move_count, e, left_click_lock, block)
        GLib.timeout_add(timeout,handle_right_click)
    else:
        pressed = False
        block = False
        abs_cur_x = -1
        abs_cur_y = -1
        print("release", btime, move_count, e, left_click_lock, block)
        if left_click_lock and not block:
            do_left_click()

def do_cancel_event(e, is_x):
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
        diff = abs(e.value - abs_cur_x)
        ratio = diff /abs_max_x
    else:
        diff = abs(e.value - abs_cur_y)
        ratio = diff / abs_max_y
    if ratio < 0.05:
        print("ignore-diff", diff, ratio)
        return
    print("cancel", btime, move_count, diff, ratio)
    ctime = time.time()
    block = True


@asynchronous
def listen_device(dev):
    global block, ctime, btime, num_of_touch, move_count, abs_cur_x, abs_cur_y
    # Bu kısımda eventler okunur
    for e in dev.events():
        print("event:", e,
              "device:", dev.fd.name,
              "press:", pressed,
              "block:", block,
              "lock:", left_click_lock,
              "touch:", num_of_touch,
              "count:", move_count,
              "abs_cur_x:", abs_cur_x,
              "abs_cur_y:", abs_cur_y
        )
        if not os.path.exists(dev.fd.name):
            print("Wait for enable")
            time.sleep(5)
            continue
        # multi touch parmak sayma
        if e.matches(libevdev.EV_ABS.ABS_MT_TRACKING_ID):
            if e.value == -1:
                num_of_touch -= 1
            else:
                num_of_touch += 1

        # hareket ettirilirse sağ tuş eventi iptal edilmeli
        if e.matches(libevdev.EV_ABS.ABS_X) or e.matches(libevdev.EV_ABS.ABS_Y):
            if abs_cur_x < 0:
                abs_cur_x = e.value
            if abs_cur_y < 0:
                abs_cur_y = e.value
            do_cancel_event(e, e.matches(libevdev.EV_ABS.ABS_X))
        # multi touch hareket eventi
        elif e.matches(libevdev.EV_ABS.ABS_MT_POSITION_X) or e.matches(libevdev.EV_ABS.ABS_MT_POSITION_Y):
            if abs_cur_x < 0:
                abs_cur_x = e.value
            if abs_cur_y < 0:
                abs_cur_y = e.value
            if num_of_touch == 1:
                move_count += 1
            do_cancel_event(e, e.matches(libevdev.EV_ABS.ABS_MT_POSITION_X))

        # tuşa basma eventi kontrolü
        if e.matches(libevdev.EV_KEY.BTN_LEFT) or e.matches(libevdev.EV_KEY.BTN_TOUCH):
            do_left_click_event(e)
        # multi touch eventi kontrolü
        elif e.matches(libevdev.EV_ABS.ABS_MT_TRACKING_ID):
            if num_of_touch == 0:
                e.value = 0
                move_count = 0
                do_left_click_event(e)
            elif num_of_touch == 1:
                e.value = 1
                do_left_click_event(e)
            else:
                do_cancel_event(e, None)

# dinlemeye başla
for dev in devices:
    abs_max_x = dev.absinfo[libevdev.EV_ABS.ABS_X].maximum
    abs_max_y = dev.absinfo[libevdev.EV_ABS.ABS_Y].maximum
    listen_device(dev)
# glib loopu kapanmayı engeller ve timeout_add çalışmasını sağlar.
main = GLib.MainLoop()
main.run()
