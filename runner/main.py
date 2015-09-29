#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Author  :   windpro
E-mail  :   windprog@gmail.com
Date    :   15/9/29
Desc    :   
"""
import select
import socket
import time

from icmp import ICMPPacket

SERVER_IP = None

KEEP_ALIVE = 'keeplive'

try:
    # linux name
    from select import epoll, EPOLLIN, EPOLLERR
except:
    pass

try:
    # bsd name
    from select import kqueue, kevent, KQ_EV_ADD, KQ_EV_DELETE, KQ_FILTER_READ
except:
    pass


class UdpIcmpForwarding(object):
    def __init__(self, listen_udp_port=5354, is_server=False, des_ip=None, channel_num=5000):
        """
        创建udp to icmp转发
        :param is_server:
        :param des_ip: 客户端需要设置，icmp目的地址
        :param channel_num: 不同的转发需要有不同的数字，最大为65535
        :return:
        """
        self.is_server = is_server
        if is_server:
            self.icmp_type = 0
        else:
            self.icmp_type = 8
        self.DesIp = des_ip
        self.seqno = channel_num
        self.listen_udp_port = listen_udp_port

        self.create_poll_object()

        self.icmpfd = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.getprotobyname("icmp"))
        self.register_poll(self.icmpfd)
        self.udpfd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)

        self.me_udp_addr = None
        if not is_server:
            self.udpfd.bind(("", listen_udp_port))
        else:
            self.me_udp_addr = ("localhost", listen_udp_port)
        self.register_poll(self.udpfd)

        # status field
        self.icmp_now_id = 0xffff

    def parse_icmp(self, data):
        packet = ICMPPacket(data)
        data = packet.data
        if packet.seqno == self.seqno:
            chksum = packet.chksum
            if self.is_server:
                # 可能客户端有多个ip出口
                des_ip = socket.inet_ntoa(packet.src)
                self.DesIp = des_ip
            if not data:
                return
            # 可解密，证明是正常数据，保证通路正常
            self.icmp_now_id = packet.id
            if not self.me_udp_addr:
                return
            self.udpfd.sendto(data, self.me_udp_addr)

    def run(self):
        while True:
            self.process()

    def create_poll_object(self):
        # linux
        self.epoll = epoll()

    def freebsd_create_poll_object(self):
        self.kqueue = kqueue()

    def register_poll(self, f):
        # linux
        self.epoll.register(f, EPOLLIN | EPOLLERR)

    def freebsd_register_poll(self, f):
        self.kqueue.control([kevent(f, KQ_FILTER_READ, KQ_EV_ADD)], 0)

    def unregister_poll(self, f):
        # linux
        self.epoll.unregister(f)

    def freebsd_unregister_poll(self, f):
        self.kqueue.control([kevent(f, KQ_FILTER_READ, KQ_EV_DELETE)], 0)

    def wait_poll(self, timeout=0.01):
        # linux
        return self.epoll.poll(timeout=timeout)

    def freebsd_wait_poll(self, timeout=0.01):
        for event in self.kqueue.control(None, 1, timeout):
            yield event.ident, event.filter

    def process(self):
        for fileno, event in self.wait_poll(timeout=10):
            try:
                if fileno == self.udpfd.fileno():
                    data, addr = self.tunfd.recvfrom(2048)
                    if self.me_udp_addr is None:
                        self.me_udp_addr = addr
                    ipk = ICMPPacket.create(self.icmp_type, 0, self.icmp_now_id, self.seqno, data).dumps()
                    self.icmpfd.sendto(ipk, (self.DesIp, 22))
                elif fileno == self.icmpfd.fileno():
                    buf = self.icmpfd.recv(2048)
                    self.parse_icmp(buf)
            except:
                import traceback

                print traceback.format_exc()
        else:
            ipk = ICMPPacket.create(self.icmp_type, 0, self.icmp_now_id, self.seqno, KEEP_ALIVE).dumps()
            self.icmpfd.sendto(ipk, (self.DesIp, 22))

# 根据操作系统类型选定IO多路复用方案
import platform

OS = platform.system().lower()
if OS == 'linux':
    # Linux下采用epoll 默认为这个
    pass
elif OS in ['freebsd', 'darwin']:
    # FreeBSD下采用kqueue
    UdpIcmpForwarding.create_poll_object = UdpIcmpForwarding.freebsd_create_poll_object
    UdpIcmpForwarding.register_poll = UdpIcmpForwarding.freebsd_register_poll
    UdpIcmpForwarding.unregister_poll = UdpIcmpForwarding.freebsd_unregister_poll
    UdpIcmpForwarding.wait_poll = UdpIcmpForwarding.freebsd_wait_poll

if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        SERVER_IP = sys.argv[1]

    kwargs = {
        "listen_udp_port": 5354,
        "is_server": False,
        "des_ip": None,
        "channel_num": 5000
    }
    if SERVER_IP:
        kwargs["des_ip"] = SERVER_IP
        kwargs["is_server"] = False
    else:
        kwargs["is_server"] = True

    f = UdpIcmpForwarding(**kwargs)
    f.run()
