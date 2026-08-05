// eta-click.c - UInput virtual device daemon for eta-right-click
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
static int server_fd = -1;
static volatile sig_atomic_t running = 1;
static pthread_mutex_t click_mutex = PTHREAD_MUTEX_INITIALIZER;

static void signal_handler(int sig) {
    (void)sig;
    running = 0;
}

static void cleanup(void) {
    if (uinput_fd >= 0) {
        ioctl(uinput_fd, UI_DEV_DESTROY);
        close(uinput_fd);
    }
    if (server_fd >= 0) {
        close(server_fd);
    }
    unlink(SOCKET_PATH);
}


static int setup_uinput(int fd) {
    struct uinput_user_dev udev;
    int abs_max_x = 3840;
    int abs_max_y = 2160;

    char *env_x = getenv("ETA_CLICK_RES_X");
    char *env_y = getenv("ETA_CLICK_RES_Y");
    if (env_x) abs_max_x = atoi(env_x);
    if (env_y) abs_max_y = atoi(env_y);

    if (abs_max_x <= 0) abs_max_x = 3840;
    if (abs_max_y <= 0) abs_max_y = 2160;

    // relative mouse
    if (ioctl(fd, UI_SET_EVBIT, EV_REL) < 0) return -1;

    // mouse buttons
    if (ioctl(fd, UI_SET_EVBIT, EV_KEY) < 0) return -1;
    if (ioctl(fd, UI_SET_KEYBIT, BTN_LEFT) < 0) return -1;
    if (ioctl(fd, UI_SET_KEYBIT, BTN_RIGHT) < 0) return -1;
    if (ioctl(fd, UI_SET_KEYBIT, BTN_MIDDLE) < 0) return -1;

    // ABS mouse axis
    if (ioctl(fd, UI_SET_EVBIT, EV_ABS) < 0) return -1;
    if (ioctl(fd, UI_SET_ABSBIT, ABS_X) < 0) return -1;
    if (ioctl(fd, UI_SET_ABSBIT, ABS_Y) < 0) return -1;

    // Keyboard
    for (int i = 1; i <= 245; i++) {
        if (ioctl(fd, UI_SET_KEYBIT, i) < 0) return -1;
    }

    memset(&udev, 0, sizeof(udev));
    snprintf(udev.name, sizeof(udev.name), "Amogus Virtual Device");
    udev.id.bustype = BUS_USB;
    udev.id.vendor  = 0x1923;
    udev.id.product = 0x1299;
    udev.absmin[ABS_X] = 0;
    udev.absmax[ABS_X] = abs_max_x;
    udev.absmin[ABS_Y] = 0;
    udev.absmax[ABS_Y] = abs_max_y;

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
    pthread_mutex_lock(&click_mutex);
    ssize_t ret = write(uinput_fd, &ie, sizeof(ie));
    pthread_mutex_unlock(&click_mutex);
    if (ret < 0) return -1;
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
    chmod(SOCKET_PATH, 0660);

    if (listen(fd, 5) < 0) {
        perror("listen");
        close(fd);
        return -1;
    }
    return fd;
}

int main(int argc, char **argv) {
    struct sigaction sa;
    sa.sa_handler = signal_handler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = 0;
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGTERM, &sa, NULL);

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

    printf("eta-click: shutting down\n");
    cleanup();
    return 0;
}
