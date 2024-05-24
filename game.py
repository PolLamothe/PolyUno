from socket import *
import threading
from time import sleep
import argparse

parser = argparse.ArgumentParser()
#to debug start a instance with -debug-server True and another with -debug-client True
parser.add_argument("-debug-server", dest="debug_server",action='store_true') 
parser.add_argument("-debug-client", dest="debug_client",action='store_true')
parser.add_argument("-debug",dest="debug",action='store_true')
args = parser.parse_args()

multicast_port_me = 55555
multicast_port_other = multicast_port_me

if(args.debug_server):
    multicast_port_other += 1
    args.debug = True
elif(args.debug_client):
    multicast_port_me += 1
    args.debug = True

multicast_group = "224.1.1.1"

s = socket(AF_INET, SOCK_DGRAM)
s.bind(("", multicast_port_me))
mreq = inet_aton(multicast_group) + inet_aton("0.0.0.0")
s.setsockopt(IPPROTO_IP, IP_ADD_MEMBERSHIP, mreq)

allPlayersIp = set()
readyPlayer = set()

def reportPresence():
    if(args.debug):
        print("sending presence")
    s.sendto(b"reporting presence",(multicast_group,multicast_port_other))

def waitForReport():
    while True:
        data, address = s.recvfrom(500)
        if((address[0],address[1]) not in allPlayersIp):
            allPlayersIp.add((address[0],address[1]))
            print(str((address[0],address[1])) + " is here")
            reportPresence()
        if(data == b"i'm ready"):
            if(args.debug):
                print(str((address[0],address[1])) + " is ready")
            readyPlayer.add((address[0],address[1]))

def readyToPlay():
    s.sendto(b"i'm ready",(multicast_group,multicast_port_other))
    if(args.debug):
        print("ready confirmation sent")

x = threading.Thread(target=waitForReport)
x.start()
reportPresence()
input("Press enter when you want to start playing \n")
readyToPlay()
while len(allPlayersIp) != len(readyPlayer):
    continue
print("everyone is ready")