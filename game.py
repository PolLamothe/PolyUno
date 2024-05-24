from socket import *

multicast_port = 55555
multicast_group = "224.1.1.1"

s = socket(AF_INET, SOCK_DGRAM)
s.bind(("", multicast_port))
mreq = inet_aton(multicast_group) + inet_aton("0.0.0.0")
s.setsockopt(IPPROTO_IP, IP_ADD_MEMBERSHIP, mreq)

s.sendto(b"coucou",(multicast_group,multicast_port))

while True:
    print(s.recv(1500).decode('utf-8'))