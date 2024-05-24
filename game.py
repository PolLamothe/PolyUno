from socket import *
import threading
from time import sleep
import argparse
import random
import json

def get_all_values(d):
    values = []
    
    def extract_values(obj):
        if isinstance(obj, dict):
            for value in obj.values():
                extract_values(value)
        elif isinstance(obj, list):
            for item in obj:
                extract_values(item)
        else:
            values.append(obj)
    
    extract_values(d)
    return values

def get_local_ip():
    # Créer un socket UDP
    s = socket(AF_INET, SOCK_DGRAM)
    
    # Connecter le socket à une adresse IP et un port (ici, google.com)
    s.connect(("8.8.8.8", 80))
    
    # Obtenir l'adresse IP locale
    local_ip = s.getsockname()[0]
    
    return local_ip

parser = argparse.ArgumentParser()
#to debug start a instance with -debug-server True and another with -debug-client True
parser.add_argument("-debug-server", dest="debug_server",action='store_true') 
parser.add_argument("-debug-client", dest="debug_client",action='store_true')
parser.add_argument("-debug",dest="debug",action='store_true')
args = parser.parse_args()

myIPAddr=get_local_ip()
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
allPlayersIp.add(str((myIPAddr,multicast_port_me)))
readyPlayer = set()
readyState = False
randomPlayerChoice = {}

def reportPresence():
    if(args.debug):
        print("sending presence")
    s.sendto(json.dumps({"api":"i'm here"}).encode(),(multicast_group,multicast_port_other))
    if(readyState):
        s.sendto(json.dumps({"api":"i'm ready"}).encode(),(multicast_group,multicast_port_other))

def listen():
    while True:
        data, address = s.recvfrom(500)
        data = json.loads(data.decode())
        if(args.debug):
            print(data)
        if(str((address[0],address[1])) not in allPlayersIp):
            allPlayersIp.add(str((address[0],address[1])))
            print(str((address[0],address[1])) + " is here")
            reportPresence()
        if(data["api"] == "i'm ready"):
            print(str((address[0],address[1])) + " is ready")
            readyPlayer.add((address[0],address[1]))
        if(data["api"] == "random player choice"):
            randomPlayerChoice[str((address[0],address[1]))] = data["choice"]
            if(args.debug):
                print(randomPlayerChoice)

def readyToPlay():
    readyPlayer.add(str((myIPAddr,multicast_port_me)))
    s.sendto(json.dumps({"api":"i'm ready"}).encode(),(multicast_group,multicast_port_other))
    if(args.debug):
        print("ready confirmation sent")

def waitingRoom():
    input("Press enter when you want to start playing \n")
    readyToPlay()
    while len(allPlayersIp) != len(readyPlayer):
        continue
    print("everyone is ready")

x = threading.Thread(target=listen)
x.start()
reportPresence()
waitingRoom()

allCard = ["0","1","2","3","4","5","6","7","8","9","invert","+2","+4","colorChange","pass"]
color = ["red","green","blue","yellow"]
PlayersCard = {}

for player in allPlayersIp:
    PlayersCard[str(player)] = set()

def pickARandomPlayer():
    x = threading.Thread(target=listen)
    x.start()
    choice = random.choice(list(allPlayersIp))
    randomPlayerChoice[str((myIPAddr,multicast_port_me))] = choice
    s.sendto(json.dumps({"api":"random player choice","choice":choice}).encode(),(multicast_group,multicast_port_other))
    while len(randomPlayerChoice) != len(allPlayersIp):
        continue
    result = get_all_values(randomPlayerChoice)
    for player in result:
        if(result.count(player) > 1):
            return player
    return pickARandomPlayer()

def getAllCardSum():
    count = 0
    for player in allPlayersIp:
        count += PlayersCard[str(player)]
    return count

def chooseAllPlayersDeck():
    while(getAllCardSum() < len(allPlayersIp)*8):
        continue



print(pickARandomPlayer())