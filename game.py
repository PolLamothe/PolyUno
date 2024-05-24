from socket import *
import threading
import argparse

parser = argparse.ArgumentParser()
#to debug start a instance with -debug-server True and another with -debug-client True
parser.add_argument("-debug-server", dest="debug_server",default=False,type=bool) 
parser.add_argument("-debug-client", dest="debug_client",default=False,type=bool)
args = parser.parse_args()

multicast_port_me = 55555
multicast_port_other = multicast_port_me

if(args.debug_server):
    multicast_port_other += 1
elif(args.debug_client):
    multicast_port_me += 1

multicast_group = "224.1.1.1"

s = socket(AF_INET, SOCK_DGRAM)
s.bind(("", multicast_port_me))
mreq = inet_aton(multicast_group) + inet_aton("0.0.0.0")
s.setsockopt(IPPROTO_IP, IP_ADD_MEMBERSHIP, mreq)

allPlayersIp = set()

def reportPresence():
    print("sending presence")
    s.sendto(b"reporting presence",(multicast_group,multicast_port_other))

def waitForReport():
    while True:
        print("waitingForReport")
        data, address = s.recvfrom(4)
        if((address[0],address[1]) not in allPlayersIp):
            allPlayersIp.add((address[0],address[1]))
            reportPresence()
            print(allPlayersIp)

x = threading.Thread(target=waitForReport)
x.start()
reportPresence()