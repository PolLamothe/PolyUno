import json
from socket import *

from textual.message import Message


def get_local_ip():
    # Connecte un socket à google.com pour obtenir l'adresse IP locale
    tmp_sock = socket(AF_INET, SOCK_DGRAM)
    tmp_sock.connect(("8.8.8.8", 80))
    local_ip = tmp_sock.getsockname()[0]
    return local_ip


class NetworkSocket:
    def __init__(self, args):
        self.args = args
        self.myIPAddr = get_local_ip()
        self.multicast_port_me = 55555
        self.multicast_port_other = self.multicast_port_me
        self.multicast_group = "224.1.1.1"

        if self.args.debug_server:
            self.multicast_port_other += 1
        elif self.args.debug_client:
            self.multicast_port_me += 1

        self.sock = socket(AF_INET, SOCK_DGRAM)
        self.sock.bind(("", self.multicast_port_me))
        mreq = inet_aton(self.multicast_group) + inet_aton("0.0.0.0")
        self.sock.setsockopt(IPPROTO_IP, IP_ADD_MEMBERSHIP, mreq)

        self.allPlayersIp = set()
        self.allPlayersIp.add(str((self.myIPAddr, self.multicast_port_me)))
        self.readyPlayer = set()
        self.readyState = False
        self.playersPseudo = {}
        self.discover_player = True

    def listen(self, event):
        while True:
            data, address = self.sock.recvfrom(2048)
            data = json.loads(data.decode())
            if self.args.debug:
                print("Debug -->" + str(data))
            # Skip if we receive our request
            if str((address[0], address[1])) == str((self.myIPAddr, self.multicast_port_me)):
                continue
            if str((address[0], address[1])) not in self.allPlayersIp and self.discover_player:
                self.allPlayersIp.add(str((address[0], address[1])))
                event(address, data)
                self.report_presence()
            self.handle_api(data, address)

    def handle_api(self, data, address):
        pass

    def report_presence(self):
        # Send presence on multicast group
        if self.args.debug:
            print("Debug --> sending presence")
        self.sock.sendto(json.dumps({
            "api": "i'm here",
            "data": self.playersPseudo[str((self.myIPAddr, self.multicast_port_me))]
        }).encode(), (self.multicast_group, self.multicast_port_other))

        if self.readyState:
            self.sock.sendto(json.dumps({
                "api": "i'm ready"
            }).encode(), (self.multicast_group, self.multicast_port_other))

    def ready_to_play(self):
        if self.args.debug:
            print("Debug --> ready confirmation sent")
        self.readyPlayer.add(str((self.myIPAddr, self.multicast_port_me)))
        self.sock.sendto(json.dumps({
            "api": "i'm ready"
        }).encode(), (self.multicast_group, self.multicast_port_other))

    def send_pseudo(self, pseudo):
        self.sock.sendto(json.dumps({
            "api": "pseudo", "data": pseudo
        }).encode(), (self.multicast_group, self.multicast_port_other))
        self.playersPseudo[str((self.myIPAddr, self.multicast_port_me))] = pseudo

    def is_ready(self, player):
        return player in self.readyPlayer
