import os
from socket import *
import threading
from time import sleep
import argparse
import random
import json

from pynput import keyboard
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from pynput.keyboard import Key, Listener

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
currentCard = None
playerThatShouldPioche = None
malusPlayer = None
oneCardPlayer = False
playersPseudo = {}

def reportPresence():
    if(args.debug):
        print("sending presence")
    s.sendto(json.dumps({"api":"i'm here","data":playersPseudo[str((myIPAddr,multicast_port_me))]}).encode(),(multicast_group,multicast_port_other))
    if(readyState):
        s.sendto(json.dumps({"api":"i'm ready"}).encode(),(multicast_group,multicast_port_other))


def handle_api(data, addr):
    global currentCard
    global playerThatShouldPioche
    global malusPlayer
    global oneCardPlayer
    # Handle API calls with data
    if(data["api"] == "i'm here"):
        allPseudo = []
        for pseudo in playersPseudo:
            allPseudo.append(playersPseudo[pseudo])
        if(data["data"] in allPseudo):
            return
        if(str((addr[0],addr[1])) in playersPseudo):
            return
        playersPseudo[str((addr[0],addr[1]))] = data["data"]
        console.print(" 👋 " + getPseudo(str((addr[0],addr[1]))) + " is here")
    elif data["api"] == "i'm ready":
        console.print("[bold green] ✅ " + getPseudo(str((addr[0], addr[1]))) + " is ready !")
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
            if(args.debug):print("ce n'es pas le tour de ce joueur")
            return
        if(playersDeck[str((addr[0],addr[1]))].count(data["data"]["card"]) == 0):#if the player try to play a card he don't have
            if(data["data"]["card"]["card"] in ["colorChange","+4"]):
                cardCopy = data["data"]["card"].copy()
                cardCopy["color"] = None
                if(playersDeck[str((addr[0],addr[1]))].count(cardCopy) == 0):
                    if(args.debug):print("le joueur à essayé de jouer une carte qu'il n'a pas")
                    return
            else : 
                if(args.debug):print("le joueur à essayé de jouer une carte qu'il n'a pas")
                return
        Y = threading.Thread(target=placeCard,args=[str(addr),data["data"]["card"]])
        Y.start()
    elif data["api"] == "firstCard":
        if(str((addr[0],addr[1])) != playersOrder[len(playersOrder)-1]):#if the player trying to play is not the last player to play
            return
        currentCard = data["data"]
    elif data["api"] == "askPioche":
        if(canPlayerPlay(str((addr[0],addr[1])))):
            if(args.debug):print("un joueur a essayer de piocher alors qu'il pouvait jouer")
            return
        playerThatShouldPioche = str((addr[0],addr[1]))
        if(amIThePlayerThatChooseCard(playerThatShouldPioche)):#if i'm the player that have to choose the card
            choice = getARandomCard()
            s.sendto(json.dumps({"api":"givePioche","card":choice}).encode(),(multicast_group,multicast_port_other))
            pioche(str((addr[0],addr[1])),choice)
        else:
            print("")
    elif data["api"] == "givePioche":
        while(playerThatShouldPioche == None):
            continue
        otherPlayerIndex = playersOrder.index(playerThatShouldPioche)
        playerIndex = playersOrder.index(str((addr[0],addr[1])))
        otherPlayerIndex += 1
        if(otherPlayerIndex >= len(playersOrder)):
            otherPlayerIndex = 0
        if(playerIndex != otherPlayerIndex):#if the player trying to give the card is not the good one
            if(args.debug):print("le joueur qui a essayer de fournir la carte piochée n'est pas le bon")
            return
        pioche(str((addr[0],addr[1])),data["card"])
    elif data["api"] == "askMalus":
        if(malusPlayer == None):#if no one need to draw
            if(args.debug):print("personne n'a de malus")
            return
        if(malusPlayer != str((addr[0],addr[1]))):#if the player asking the malus is not the good one
            if(args.debug):print("le joueur qui demande un malus n'est pas le bon")
            return
        if(amIThePlayerThatChooseCard(str((addr[0],addr[1])))):
            if(args.debug):print("i have to choose the malus")
            result = []
            for i in range(int(data["cardsNumber"])):
                result.append(getARandomCard())
            s.sendto(json.dumps({"api":"giveMalus","cards":result}).encode(),(multicast_group,multicast_port_other))
            malusPioche(str((addr[0],addr[1])),result)
    elif data["api"] == "giveMalus":
        otherPlayerIndex = playersOrder.index(malusPlayer)
        playerIndex = playersOrder.index(str((addr[0],addr[1])))
        otherPlayerIndex += 1
        if(otherPlayerIndex >= len(playersOrder)):
            otherPlayerIndex = 0
        if(playerIndex != otherPlayerIndex):#if the player trying to give the card is not the good one
            if(args.debug):print("le joueur qui a essayer de fournir les cartes malus n'est pas le bon")
            return
        malusPioche(malusPlayer,data["cards"])
    elif data["api"] == "contreUno":
        if(not oneCardPlayer):
            return
        if(data["data"] == "uno" and str((addr[0],addr[1])) == playersOrder[currentPlayerIndex]):
            oneCardPlayer = False
            print(getPseudo(str((addr[0],addr[1])))+" a dit uno ! (appuyez sur une entrée)")
            return
        elif(data["data"] == "contre uno" and str((addr[0],addr[1])) != playersOrder[currentPlayerIndex]):#if the player who counter is not the one who have only one card
            malusPlayer =  playersOrder[currentPlayerIndex]
            oneCardPlayer = False
            print(getPseudo(str((addr[0],addr[1])))+" a dit contre uno ! (appuyez sur une entrée)")
            if(str((myIPAddr,multicast_port_me)) == playersOrder[currentPlayerIndex]):#if i'm the player that have to draw
                s.sendto(json.dumps({"api":"askMalus","cardsNumber":"2"}).encode(),(multicast_group,multicast_port_other))
        else:
            if(args.debug):print("mauvais contreUno")
                

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
            if(len(allPlayersIp) == len(readyPlayer)):
                continue
            allPlayersIp.add(str((address[0],address[1])))
            reportPresence()
        handle_api(data, address)

def readyToPlay():
    console.print("[bold green] ✅ You're ready to play")
    readyPlayer.add(str((myIPAddr,multicast_port_me)))
    s.sendto(json.dumps({"api":"i'm ready"}).encode(),(multicast_group,multicast_port_other))
    if(args.debug):
        print("ready confirmation sent")


def waitingRoom():
    console.clear()
    with console.status("[bold green]Waiting one player...") as status:
        while len(allPlayersIp) < 2:
            continue
    console.clear()
    console.print("[bold blue]\n--- Press enter when you want to start playing ---\n")
    input()
    readyToPlay()
    while len(allPlayersIp) != len(readyPlayer):
        continue
    console.print(Markdown("# Everyone is ready!"))

allCards = ["0","1","2","3","4","5","6","7","8","9","invert","+2","+4","colorChange","pass"]
color = ["red","green","blue","yellow"]

def createADeck():
    result = []
    for i in range(8):
        result.append(getARandomCard())
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
    global currentCard
    global malusPlayer
    global playersOrder
    global currentPlayerIndex
    global oneCardPlayer
    if(card["card"] in ["colorChange","+4"]):
        cardCopy = card.copy()
        cardCopy["color"] = None
        playersDeck[player].remove(cardCopy)
    else:
        playersDeck[player].remove(card)
    currentCard = card
    print(getPseudo(player) + " à joué la carte "+getStringFromCard(card)+"\n")
    if(card["card"] == "pass"):
        increasePlayerIndex()
    if(card["card"] == "+2"):
        placerIndex = playersOrder.index(player)
        otherPlayerIndex = placerIndex+1
        if(otherPlayerIndex >= len(playersOrder)):
            otherPlayerIndex = 0
        malusPlayer =  playersOrder[otherPlayerIndex]
        if(str((myIPAddr,multicast_port_me)) == malusPlayer):#if i'm the player that take the malus
            s.sendto(json.dumps({"api":"askMalus","cardsNumber":"2"}).encode(),(multicast_group,multicast_port_other))
        while malusPlayer != None:
            continue
    if(card["card"] == "+4"):
        placerIndex = playersOrder.index(player)
        otherPlayerIndex = placerIndex+1
        if(otherPlayerIndex >= len(playersOrder)):
            otherPlayerIndex = 0
        malusPlayer =  playersOrder[otherPlayerIndex]
        if(str((myIPAddr,multicast_port_me)) == malusPlayer):#if i'm the player that take the malus
            s.sendto(json.dumps({"api":"askMalus","cardsNumber":"4"}).encode(),(multicast_group,multicast_port_other))
        while malusPlayer != None:
            continue
    if(card["card"] == "invert"):
        reversed(playersOrder)
        currentPlayerIndex = len(playersOrder)-currentPlayerIndex-1
    if(len(playersDeck[playersOrder[currentPlayerIndex]]) == 1):
        oneCardPlayer = True
        print(getPseudo(playersOrder[currentPlayerIndex])+" n'a plus que 1 carte \n")
        while(oneCardPlayer):
            choice = input("Qu'avez vous à lui dire : ")
            if(choice == "uno" and str((myIPAddr,multicast_port_me)) == playersOrder[currentPlayerIndex]):
                oneCardPlayer = False
                s.sendto(json.dumps({"api":"contreUno","data":choice}).encode(),(multicast_group,multicast_port_other))
                continue
            elif(choice == "contre uno" and str((myIPAddr,multicast_port_me)) != playersOrder[currentPlayerIndex]):#if the player who counter is not the one who have only one card
                malusPlayer =  playersOrder[currentPlayerIndex]
                oneCardPlayer = False
                s.sendto(json.dumps({"api":"contreUno","data":choice}).encode(),(multicast_group,multicast_port_other))
        while(malusPlayer != None):
            continue
    increasePlayerIndex()

def printPlayerDeck(placable=False):
    print("voici toute vos cartes : \n")
    for card in playersDeck[str((myIPAddr,multicast_port_me))]:
        print(getStringFromCard(card))
    print("\nveuillez choisir une carte \n")
    cards = playersDeck[str((myIPAddr,multicast_port_me))]
    if(placable):
        cards = getPlacableCard(cards)
    for i in range(len(cards)):
        print(str(i+1)+". "+getStringFromCard(cards[i]))
    print("\n")

def getPlayerInput(max):
    choice = input("votre choix : ")
    if(not choice.isnumeric()):return getPlayerInput(max)
    if(int(choice) <= 0 or int(choice) > max):return getPlayerInput(max)
    return choice

def getPlayerCardChoice():
    global playerThatShouldPioche
    if(canPlayerPlay(playersOrder[currentPlayerIndex])):
        printPlayerDeck(placable=True)
        choice = getPlayerInput(len(getPlacableCard(playersDeck[playersOrder[currentPlayerIndex]])))
        print("")
        card = getPlacableCard(playersDeck[playersOrder[currentPlayerIndex]])[int(choice)-1].copy()
        if(getPlacableCard(playersDeck[playersOrder[currentPlayerIndex]])[int(choice)-1]["color"] == None):
            print("vous devez choisir la couleur \n")
            for i in range(len(color)):
                print(str(i+1)+". "+color[i])
            colorChoice = getPlayerInput(len(color))
            card["color"] = color[int(colorChoice)-1]
        return card
    else:
        print("vous ne pouvez poser aucune carte, vous devez donc piocher")
        playerThatShouldPioche = str((myIPAddr,multicast_port_me))
        s.sendto(json.dumps({"api":"askPioche"}).encode(),(multicast_group,multicast_port_other))
        while playerThatShouldPioche != None:
            continue
        return None

def isGameOver():
    for player in playersDeck:
        if(len(playersDeck[player]) == 0):
            return True
    return False

def getStringFromCard(jsonCard):
    if(jsonCard["color"] != None):
        return jsonCard["card"]+" de couleur "+jsonCard["color"]
    return jsonCard["card"]

def chooseFirstCard():
    global currentCard
    choice = getARandomCard()
    s.sendto(json.dumps({"api":"firstCard","data":choice}).encode(),(multicast_group,multicast_port_other))
    currentCard = choice

def getPlacableCard(cards):
    result = []
    for card in cards:
        if(str(card["color"]) == "None"):
            result.append(card)
        elif(card["color"] == currentCard["color"]):
            result.append(card)
        elif(card["card"] == currentCard["card"]):
            result.append(card)
    return result

def getARandomCard():
    result = {"card":random.choice(allCards),"color":random.choice(color)}
    if(result["card"] in ["colorChange","+4"]):
        result["color"] = None
    return result

def canPlayerPlay(player):
    return len(getPlacableCard(playersDeck[player])) > 0

def pioche(player,card):
    global playerThatShouldPioche
    playersDeck[playerThatShouldPioche].append(card)
    if(playerThatShouldPioche == str((myIPAddr,multicast_port_me))):
        print("vous avez pioché la carte : "+getStringFromCard(card))
    else:
        print(getPseudo(player)+" à pioché")
    print("")
    playerThatShouldPioche = None
    increasePlayerIndex()

def malusPioche(player,cards):
    global malusPlayer
    for card in cards:
        playersDeck[player].append(card)
        if(player == str((myIPAddr,multicast_port_me))):
            print("vous avez pioché "+getStringFromCard(card))
        else:
            print(getPseudo(player)+" a pioché une carte")
    print("")
    malusPlayer = None

def amIThePlayerThatChooseCard(otherPlayer):
    otherPlayerIndex = playersOrder.index(otherPlayer)
    myIndex = playersOrder.index(str((myIPAddr,multicast_port_me)))
    otherPlayerIndex += 1
    if(otherPlayerIndex >= len(playersOrder)):
        otherPlayerIndex = 0
    return myIndex == otherPlayerIndex

def askPseudo():
    # UI
    def ui(error):
        console.clear()
        console.print(
            "[red]  _____      _       _    _             \n |  __ \    | |     | |  | |            \n | |__) |__ | |_   _| |  | |_ __   ___  \n |  ___/ _ \| | | | | |  | | '_ \ / _ \ \n | |  | (_) | | |_| | |__| | | | | (_) |\n |_|   \___/|_|\__, |\____/|_| |_|\___/ \n                __/ |                   \n               |___/                    ")
        console.print("\n\n")
        if error is True:
            console.print("[red]Error")
            console.print("\n")
        console.print("[bold]Veuillez entrer votre pseudo : [/bold]")
        c = input(">> ")
        return c

    choice = ui(False)
    allPseudo = []
    for pseudo in playersPseudo:
        allPseudo.append(playersPseudo[pseudo])
    while choice == "" or choice in allPseudo:
        choice = ui(True)
    s.sendto(json.dumps({"api":"pseudo","data":choice}).encode(),(multicast_group,multicast_port_other))
    playersPseudo[str((myIPAddr,multicast_port_me))] = choice

def getPseudo(addr):
    return playersPseudo[addr]

currentPlayerIndex = 0

askPseudo()
x = threading.Thread(target=listen)
x.start()
sleep(0.1)
reportPresence()
waitingRoom()

defineOtherPlayerDeck()
if(str((myIPAddr,multicast_port_me)) == playersOrder[len(playersOrder)-1]):
    chooseFirstCard()
while(currentCard == None):
    continue
while not isGameOver():
    if(playersOrder[currentPlayerIndex] == str((myIPAddr,multicast_port_me))):
        choice = getPlayerCardChoice()
        if(choice != None):
            s.sendto(json.dumps({"api":"play","data":{"card":choice}}).encode(),(multicast_group,multicast_port_other))
            placeCard(str((myIPAddr,multicast_port_me)),choice)
print("la partie est fini")