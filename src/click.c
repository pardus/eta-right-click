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
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/stat.h>
#include <signal.h>
#include <pthread.h>

#define SOCKET_PATH "/run/eta-click.sock"

struct event {
    int ev_type;
    int ev_code;
    int ev_value;
};

static int uinput_fd = -1;
static volatile sig_atomic_t running = 1;


static int setup_uinput(int fd) {
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
    udev.absmax[ABS_X] = 3840;
    udev.absmin[ABS_Y] = 0;
    udev.absmax[ABS_Y] = 2160;

    if (write(fd, &udev, sizeof(udev)) < 0) return -1;
    if (ioctl(fd, UI_DEV_CREATE) < 0) return -1;
    return 0;
}

static int emit(__u16 type, __u16 code, __s32 value) {
    struct input_event ie;
    memset(&ie, 0, sizeof(ie));
    ie.type = type;
    ie.code = code;
    ie.value = value;
    if (write(uinput_fd, &ie, sizeof(ie)) < 0) return -1;
    return 0;
}

#define esync() emit(EV_SYN, SYN_REPORT, 0)

static void *handle_client(void *arg) {
    int client_fd = (int)(intptr_t)arg;
    struct event ev;
    ssize_t n;
    while((n = read(client_fd, &ev, sizeof(ev))) == sizeof(ev)){
        printf("EV: %d %d %d\n", ev.ev_type, ev.ev_code, ev.ev_value);
        emit(ev.ev_type, ev.ev_code, ev.ev_value);
    }
    close(client_fd);
    return NULL;
}

static int setup_socket(void) {
    struct sockaddr_un addr;
    int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) {
        perror("socket");
        return -1;
    }

    unlink(SOCKET_PATH);
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, SOCKET_PATH, sizeof(addr.sun_path) - 1);

    if (bind(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("bind");
        close(fd);
        return -1;
    }
    chmod(SOCKET_PATH, 0666);

    if (listen(fd, 5) < 0) {
        perror("listen");
        close(fd);
        return -1;
    }
    return fd;
}

int main(int argc, char **argv) {
    int server_fd;


    uinput_fd = open("/dev/uinput", O_WRONLY | O_NONBLOCK);
    if (uinput_fd < 0) {
        perror("open /dev/uinput");
        return 1;
    }

    if (setup_uinput(uinput_fd) < 0) {
        perror("setup_uinput");
        close(uinput_fd);
        return 1;
    }

    server_fd = setup_socket();
    if (server_fd < 0) {
        close(uinput_fd);
        return 1;
    }

    printf("eta-click: listening on %s\n", SOCKET_PATH);

    while (running) {
        struct sockaddr_un client_addr;
        socklen_t client_len = sizeof(client_addr);
        int client_fd = accept(server_fd, (struct sockaddr *)&client_addr, &client_len);
        if (client_fd < 0) {
            if (errno == EINTR) continue;
            perror("accept");
            break;
        }
        pthread_t th;
        pthread_attr_t attr;
        pthread_attr_init(&attr);
        pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_DETACHED);
        pthread_create(&th, &attr, handle_client, (void *)(intptr_t)client_fd);
        pthread_attr_destroy(&attr);
    }

    unlink(SOCKET_PATH);
    close(server_fd);
    close(uinput_fd);
    return 0;
}
