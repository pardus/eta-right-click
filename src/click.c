// uinput_abs_mouse.c
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <linux/uinput.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>

static int setup_uinput(int fd, int max_x, int max_y) {
    struct uinput_user_dev udev;
    if (ioctl(fd, UI_SET_EVBIT, EV_REL) < 0) return -1;

    if (ioctl(fd, UI_SET_EVBIT, EV_KEY) < 0) return -1;
    if (ioctl(fd, UI_SET_KEYBIT, BTN_LEFT) < 0) return -1;
    if (ioctl(fd, UI_SET_KEYBIT, BTN_RIGHT) < 0) return -1;
    if (ioctl(fd, UI_SET_KEYBIT, BTN_MIDDLE) < 0) return -1;

    if (ioctl(fd, UI_SET_EVBIT, EV_ABS) < 0) return -1;
    if (ioctl(fd, UI_SET_ABSBIT, ABS_X) < 0) return -1;
    if (ioctl(fd, UI_SET_ABSBIT, ABS_Y) < 0) return -1;

    memset(&udev, 0, sizeof(udev));
    snprintf(udev.name, sizeof(udev.name), "Amogus Right Click");
    udev.id.bustype = BUS_USB;
    udev.id.vendor  = 0x1923;
    udev.id.product = 0x1299;
    udev.absmin[ABS_X] = 0;
    udev.absmax[ABS_X] = max_x;
    udev.absmin[ABS_Y] = 0;
    udev.absmax[ABS_Y] = max_y;

    if (write(fd, &udev, sizeof(udev)) < 0) return -1;
    if (ioctl(fd, UI_DEV_CREATE) < 0) return -1;
    return 0;
}

static int emit(int fd, __u16 type, __u16 code, __s32 value) {
    struct input_event ie;
    memset(&ie, 0, sizeof(ie));
    ie.type = type;
    ie.code = code;
    ie.value = value;
    if (write(fd, &ie, sizeof(ie)) < 0) return -1;
    return 0;
}

#define esync(fd) emit(fd, EV_SYN, SYN_REPORT, 0)

int main(int argc, char **argv) {
    int fd;
    int x = -1, y = -1;
    int maxx = 3840, maxy = 2160;
    int btn = BTN_LEFT;

    if (argc >= 2){
        if(strcmp(argv[1], "right") == 0){
            btn = BTN_RIGHT;
        } else if(strcmp(argv[1], "left") == 0){
            btn = BTN_LEFT;
        } else if(strcmp(argv[1], "middle") == 0){
            btn = BTN_MIDDLE;
        }
    }

    if (argc >= 3) {
        x = atoi(argv[2]);
        y = atoi(argv[3]);
    }

    printf("%d %d %d\n", x, y, btn);
    fd = open("/dev/uinput", O_WRONLY | O_NONBLOCK);
    if (fd < 0) {
        perror("open /dev/uinput");
        return 1;
    }

    if (setup_uinput(fd, maxx, maxy) < 0) {
        perror("setup_uinput");
        close(fd);
        return 1;
    }

    usleep(300000);

    // Move to absolute position
    if (x > 0 && emit(fd, EV_ABS, ABS_X, x) < 0) { perror("emit ABS_X"); }
    esync(fd);
    if (y > 0 && emit(fd, EV_ABS, ABS_Y, y) < 0) { perror("emit ABS_Y"); }
    esync(fd);
    usleep(20000);

    // Press right button
    emit(fd, EV_KEY, btn, 1);
    esync(fd);

    usleep(200000);
    // Release right button
    emit(fd, EV_KEY, btn, 0);
    esync(fd);

    ioctl(fd, UI_DEV_DESTROY);
    close(fd);
    return 0;
}
