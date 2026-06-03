import os
import socket

class NetlinkSocket(socket.socket):
    def __init__(self):
        NETLINK_KOBJECT_UEVENT = 15
        socket.socket.__init__(
            self,
            socket.AF_NETLINK,
            socket.SOCK_DGRAM,
            NETLINK_KOBJECT_UEVENT
        )
        self.bind((os.getpid(), -1))
        self.action = None

    def _parse(self):
        data = self.recv(65534)
        event = {}
        for item in data.split(b"\x00"):
            item = item.decode("utf-8", errors="ignore")
            if "=" in item:
                name = item.split("=")[0]
                event[name] = item[len(name)+1:]
        if self.action:
            self.action(event)

    def run(self):
        while True:
            self._parse()

if __name__ == '__main__':
    nls = NetlinkSocket()
    nls.action = print
    nls.run()
