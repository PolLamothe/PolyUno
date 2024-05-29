import os
from socket import *
import threading
from time import sleep
import argparse
import random
import json
from rich.console import Console
from rich.markdown import Markdown

# Init console for TUI
console = Console()

def get_local_ip():
    # Créer un socket UDP
    s = socket(AF_INET, SOCK_DGRAM)
    
    # Connecter le socket à une adresse IP et un port (ici, google.com)
    s.connect(("8.8.8.8", 80))
    
    # Obtenir l'adresse IP locale
    local_ip = s.getsockname()[0]
    
    return local_ip

parser = argparse.ArgumentParser()
# To debug start an instance with -debug-server True and another with -debug-client True
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
playersOrder = []
playersDeck = {}

def reportPresence():
    if(args.debug):
        print("sending presence")
    s.sendto(json.dumps({"api":"i'm here"}).encode(),(multicast_group,multicast_port_other))
    if(readyState):
        s.sendto(json.dumps({"api":"i'm ready"}).encode(),(multicast_group,multicast_port_other))


def handle_api(data, addr):
    # Handle API calls with data
    if data["api"] == "i'm ready":
        console.print(str((addr[0], addr[1])) + "[bold green] is ready")
        readyPlayer.add((addr[0], addr[1]))
    elif data["api"] == "deck":
        while len(playersOrder) == 0:
            continue
        index = playersOrder.index(data["data"]["player"])
        if index == 0:
            index = len(playersOrder) - 1
        else:
            index -= 1
        if str((addr[0], addr[1])) == playersOrder[index]:
            playersDeck[data["data"]["player"]] = data["data"]["deck"]
    elif data["api"] == "play":
        if(str((addr[0],addr[1])) != playersOrder[currentPlayerIndex]):#if the player trying to play is not the good one
            return
        if(playersDeck[str((addr[0],addr[1]))].count(data["data"]["card"]) == 0):
            return
        placeCard(str(addr),data["data"]["card"])
        increasePlayerIndex()

def listen():
    global otherPlayersDeckVersions
    global playersOrder
    while True:
        data, address = s.recvfrom(2048)
        if(str((address[0],address[1])) == str((myIPAddr,multicast_port_me))):
            continue
        data = json.loads(data.decode())
        if(args.debug):
            print(data)
        if(str((address[0],address[1])) not in allPlayersIp):
            if(readyState == True):
                continue
            allPlayersIp.add(str((address[0],address[1])))
            console.print(str((address[0],address[1])) + " is here")
            reportPresence()
        handle_api(data, address)

def readyToPlay():
    readyPlayer.add(str((myIPAddr,multicast_port_me)))
    s.sendto(json.dumps({"api":"i'm ready"}).encode(),(multicast_group,multicast_port_other))
    if(args.debug):
        print("ready confirmation sent")

def waitingRoom():
    while(len(allPlayersIp) < 2):
        continue
    input("Press enter when you want to start playing \n")
    readyToPlay()
    while len(allPlayersIp) != len(readyPlayer):
        continue
    console.print(Markdown("# Everyone is ready!"))

allCards = ["0","1","2","3","4","5","6","7","8","9","invert","+2","+4","colorChange","pass"]
color = ["red","green","blue","yellow"]

def createADeck():
    result = []
    for i in range(8):
        result.append(json.dumps({"card":random.choice(allCards),"color":random.choice(color)}))
    return result

def defineOtherPlayerDeck():
    global playersOrder
    global playersDeck
    playersOrder = sorted(list(allPlayersIp))
    index = playersOrder.index(str((myIPAddr,multicast_port_me)))
    if(index == len(allPlayersIp)-1):
        index = 0
    else:
        index += 1
    if(args.debug):
        print("je choisis le deck de : "+playersOrder[index])
    deck = createADeck()
    playersDeck[playersOrder[index]] = deck
    s.sendto(json.dumps({"api":"deck","data":{"player":playersOrder[index],"deck":deck}}).encode(),(multicast_group,multicast_port_other))
    while(len(playersDeck) != len(allPlayersIp)):
        continue

def isGameFinished():
    for player in playersDeck:
        if(len(playersDeck[player]) == 0):
            return True
    return False

def increasePlayerIndex():
    global currentPlayerIndex
    if(currentPlayerIndex != len(playersOrder)-1):
        currentPlayerIndex += 1
    else:
        currentPlayerIndex = 0

def placeCard(player,card):
    playersDeck[player].remove(card)
    print(player + " à joué la carte "+card)

def printPlayerDeck():
    #TODO
    print("veuillez choisir une carte \n")
    for i in range(len(playersDeck[str((myIPAddr,multicast_port_me))])):
        print(str(i+1)+". "+playersDeck[str((myIPAddr,multicast_port_me))][i])
    print("\n")

def getPlayerCardChoice():
    printPlayerDeck()
    choice = input("votre choix : ")
    while(int(choice) < 0 or int(choice) > len(playersDeck[playersOrder[currentPlayerIndex]])):
        choice = input("votre choix : ")
    return playersDeck[playersOrder[currentPlayerIndex]][int(choice)-1]

def isGameOver():
    for player in playersDeck:
        if(len(playersDeck[player]) == 0):
            return True
    return False

currentPlayerIndex = 0

x = threading.Thread(target=listen)
x.start()
sleep(0.1)
reportPresence()
waitingRoom()

defineOtherPlayerDeck()
while not isGameOver():
    if(playersOrder[currentPlayerIndex] == str((myIPAddr,multicast_port_me))):
        choice = getPlayerCardChoice()
        s.sendto(json.dumps({"api":"play","data":{"card":choice}}).encode(),(multicast_group,multicast_port_other))
        placeCard(str((myIPAddr,multicast_port_me)),choice)
        increasePlayerIndex()
print("la partie est fini")