from socket import *
import threading
from time import sleep
import argparse
import random
import json
from rich.console import Console
from rich.markdown import Markdown

# Init console for TUI
console = Console(highlight=False)


def get_local_ip():
    """
    Permet de récupérer l'IP locale de l'utilisateur en se connectant au DNS de Google.
    :return: L'IP locale de l'utilisateur
    """
    # Créer un socket UDP
    s = socket(AF_INET, SOCK_DGRAM)
    # Connecter le socket à une adresse IP et un port (ici, google.com)
    s.connect(("8.8.8.8", 80))
    # Obtenir l'adresse IP locale
    local_ip = s.getsockname()[0]
    return local_ip


# Parse arguments :
# To debug start an instance with -debug-server and another with -debug-client
parser = argparse.ArgumentParser()
parser.add_argument("-debug-server", dest="debug_server", action='store_true')
parser.add_argument("-debug-client", dest="debug_client", action='store_true')
parser.add_argument("-debug", dest="debug", action='store_true')
args = parser.parse_args()

# Définir l'IP et le port
myIPAddr = get_local_ip()
multicast_port_me = 55555
multicast_port_other = multicast_port_me

# Changer le port si l'exécution se fait en local
if args.debug_server:
    multicast_port_other += 1
elif args.debug_client:
    multicast_port_me += 1

# IP du groupe multicast
multicast_group = "224.1.1.1"

# Création du socket UDP
s = socket(AF_INET, SOCK_DGRAM)
s.bind(("", multicast_port_me))
mreq = inet_aton(multicast_group) + inet_aton("0.0.0.0")
s.setsockopt(IPPROTO_IP, IP_ADD_MEMBERSHIP, mreq)

# Variables globales
allPlayersIp = set()
allPlayersIp.add(str((myIPAddr, multicast_port_me)))
readyPlayer = set()
readyState = False
playersOrder = []
playersDeck = {}
currentCard = None
playerThatShouldPioche = None
malusPlayer = None
oneCardPlayer = False
playersPseudo = {}

# Cartes
allCards = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "invert", "+2", "+4", "colorChange", "pass"]
color = ["red", "green", "blue", "yellow"]
cardsProbability = {"+4": 4, "pass": 8, "invert": 8, "+2": 8}

# Probabilité de pioche des cartes
for i in range(10):
    cardsProbability[str(i)] = 8
cardsChoice = []
for i in cardsProbability:
    for x in range(cardsProbability[i]):
        cardsChoice.append(i)


def reportPresence():
    """
    Envoi un signal de présence en multicast
    """
    if args.debug:
        print("sending presence")
    s.sendto(json.dumps({"api": "i'm here", "data": playersPseudo[str((myIPAddr, multicast_port_me))]}).encode(),
             (multicast_group, multicast_port_other))
    if readyState:
        s.sendto(json.dumps({"api": "i'm ready"}).encode(), (multicast_group, multicast_port_other))


def handle_api(data, addr):
    """
    Permet de récupérer et traiter les requêtes entrantes de l'API
    :param data: Les données de la requête
    :param addr: L'adresse de la source
    """
    global currentCard
    global playerThatShouldPioche
    global malusPlayer
    global oneCardPlayer
    # Handle API calls with data
    if data["api"] == "i'm here":
        allPseudo = []
        for pseudo in playersPseudo:
            allPseudo.append(playersPseudo[pseudo])
        if data["data"] in allPseudo:
            return
        if str((addr[0], addr[1])) in playersPseudo:
            return
        playersPseudo[str((addr[0], addr[1]))] = data["data"]
        console.print(" 👋 " + getPseudo(str((addr[0], addr[1]))) + " is here\n")
    elif data["api"] == "i'm ready":
        console.print("[bold green] ✅ " + getPseudo(str((addr[0], addr[1]))) + " is ready !\n")
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
        if str((addr[0], addr[1])) != playersOrder[currentPlayerIndex]:
            # if the player trying to play is not the good one
            if args.debug: print("ce n'es pas le tour de ce joueur")
            return
        if (playersDeck[str((addr[0], addr[1]))].count(
                data["data"]["card"]) == 0):  # if the player try to play a card he doesn't have
            if data["data"]["card"]["card"] in ["colorChange", "+4"]:
                cardCopy = data["data"]["card"].copy()
                cardCopy["color"] = None
                if playersDeck[str((addr[0], addr[1]))].count(cardCopy) == 0:
                    if args.debug: print("le joueur à essayé de jouer une carte qu'il n'a pas")
                    return
            else:
                if args.debug: print("le joueur à essayé de jouer une carte qu'il n'a pas")
                return
        Y = threading.Thread(target=placeCard, args=[str(addr), data["data"]["card"]])
        Y.start()
    elif data["api"] == "firstCard":
        if str((addr[0], addr[1])) != playersOrder[len(playersOrder) - 1]:
            # if the player trying to play is not the last player to play
            return
        currentCard = data["data"]
        console.print("\n[bold] ➡️ The last card played is: [/bold]", getStringFromCard(currentCard), "\n")
    elif data["api"] == "askPioche":
        #If the request is a player asking a Malus
        if canPlayerPlay(str((addr[0], addr[1]))):
            if args.debug:
                print("un joueur a essayer de piocher alors qu'il pouvait jouer")
            return
        playerThatShouldPioche = str((addr[0], addr[1]))
        if amIThePlayerThatChooseCard(playerThatShouldPioche):  # if i'm the player that have to choose the card
            choice = getARandomCard()
            s.sendto(json.dumps({"api": "givePioche", "card": choice}).encode(),
                     (multicast_group, multicast_port_other))
            pioche(str((addr[0], addr[1])), choice)
        else:
            print("")
    elif data["api"] == "givePioche":
        #If the request contain the card have been drawed
        while playerThatShouldPioche == None:
            continue
        otherPlayerIndex = playersOrder.index(playerThatShouldPioche)
        playerIndex = playersOrder.index(str((addr[0], addr[1])))
        otherPlayerIndex += 1
        if otherPlayerIndex >= len(playersOrder):
            otherPlayerIndex = 0
        if playerIndex != otherPlayerIndex:  # if the player trying to give the card is not the good one
            if args.debug: print("le joueur qui a essayer de fournir la carte piochée n'est pas le bon")
            return
        pioche(str((addr[0], addr[1])), data["card"])
    elif data["api"] == "askMalus":
        #If the request is a player asking a Malus
        if malusPlayer == None:  # if no one need to draw
            if args.debug: print("personne n'a de malus")
            return
        if malusPlayer != str((addr[0], addr[1])):  # if the player asking the malus is not the good one
            if args.debug: print("le joueur qui demande un malus n'est pas le bon")
            return
        if amIThePlayerThatChooseCard(str((addr[0], addr[1]))):
            if args.debug:
                print("i have to choose the malus")
            result = []
            for i in range(int(data["cardsNumber"])):
                result.append(getARandomCard())
            s.sendto(json.dumps({"api": "giveMalus", "cards": result}).encode(),
                     (multicast_group, multicast_port_other))
            malusPioche(str((addr[0], addr[1])), result)
    elif data["api"] == "giveMalus":
        #If the request contain the card have been drawed
        otherPlayerIndex = playersOrder.index(malusPlayer)
        playerIndex = playersOrder.index(str((addr[0], addr[1])))
        otherPlayerIndex += 1
        if otherPlayerIndex >= len(playersOrder):
            otherPlayerIndex = 0
        if playerIndex != otherPlayerIndex:  # if the player trying to give the card is not the good one
            if args.debug: print("le joueur qui a essayer de fournir les cartes malus n'est pas le bon")
            return
        malusPioche(malusPlayer, data["cards"])
    elif data["api"] == "contreUno":
        if not oneCardPlayer:
            return
        if data["data"] == "uno" and str((addr[0], addr[1])) == playersOrder[currentPlayerIndex]:
            oneCardPlayer = False
            console.print("[italic] " + getPseudo(str((addr[0], addr[1]))) + "[/italic] said UNO! (press enter)")
            return
        elif (data["data"] == "contre uno" and str((addr[0], addr[1])) != playersOrder[
            currentPlayerIndex]):  # if the player who counter is not the one who have only one card
            malusPlayer = playersOrder[currentPlayerIndex]
            oneCardPlayer = False
            console.print(
                "[italic] " + getPseudo(str((addr[0], addr[1]))) + "[/italic] said 'contre' UNO! (press enter)")
            if (str((myIPAddr, multicast_port_me)) == playersOrder[
                currentPlayerIndex]):  # if i'm the player that have to draw
                s.sendto(json.dumps({"api": "askMalus", "cardsNumber": "2"}).encode(),
                         (multicast_group, multicast_port_other))
        else:
            if args.debug: print("mauvais contreUno")


def listen():
    """
    Thread qui écoute les requêtes entrantes
    """
    global otherPlayersDeckVersions
    global playersOrder
    while True:
        data, address = s.recvfrom(2048)
        if str((address[0], address[1])) == str((myIPAddr, multicast_port_me)): #if the sender is myself
            continue
        data = json.loads(data.decode())
        if args.debug:
            print(data)
        if str((address[0], address[1])) not in allPlayersIp:#if the sender is a new player
            if len(allPlayersIp) == len(readyPlayer):
                continue
            allPlayersIp.add(str((address[0], address[1])))
            reportPresence()#report to the new player our presence
        handle_api(data, address)


def readyToPlay():
    """
    Envoie l'information que le joueur est prêt à lancer la partie
    """
    console.print("[bold green] ✅ You're ready to play\n")
    readyPlayer.add(str((myIPAddr, multicast_port_me)))
    s.sendto(json.dumps({"api": "i'm ready"}).encode(), (multicast_group, multicast_port_other))
    if args.debug:
        print("ready confirmation sent")


def waitingRoom():
    """
    Phase d'attente d'autres joueurs à rejoindre la partie
    """
    if len(allPlayersIp) < 2:
        console.print("[bold blue] ℹ️ Waiting players\n")
    while len(allPlayersIp) < 2:
        continue
    console.print("[bold blue] ℹ️ Press enter when you want to start playing\n")
    input()
    readyToPlay()
    while len(allPlayersIp) != len(readyPlayer):
        continue
    console.print(Markdown("# Everyone ready, game on!"))
    console.clear()


def createADeck():
    """
    Crée le jeu d'un joueur avec 8 cartes
    :return: Un tableau de 8 cartes
    """
    result = []
    for i in range(8):
        result.append(getARandomCard())
    return result


def defineOtherPlayerDeck():
    """
    Choisi le jeu d'un autre joueur et informe les autres
    """
    global playersOrder
    global playersDeck
    playersOrder = sorted(list(allPlayersIp))
    index = playersOrder.index(str((myIPAddr, multicast_port_me)))
    if index == len(allPlayersIp) - 1:
        index = 0
    else:
        index += 1
    if args.debug:
        print("je choisis le deck de : " + playersOrder[index])
    deck = createADeck()
    playersDeck[playersOrder[index]] = deck
    s.sendto(json.dumps({"api": "deck", "data": {"player": playersOrder[index], "deck": deck}}).encode(),
             (multicast_group, multicast_port_other))
    while len(playersDeck) != len(allPlayersIp):
        continue


def isGameFinished():
    """
    Vérifie si la partie est terminée
    :return: Bool
    """
    for player in playersDeck:
        if len(playersDeck[player]) == 0:
            return True
    return False


def increasePlayerIndex():
    """
    Choisi l'index du prochain joueur
    """
    global currentPlayerIndex
    if currentPlayerIndex != len(playersOrder) - 1:
        currentPlayerIndex += 1
    else:
        currentPlayerIndex = 0


def placeCard(player, card):
    """
    Permet à un joueur de jouer une carte et informe les autres avec la gestion des malus.
    :param player: Le joueur de la carte.
    :param card: La carte a joué.
    """
    global currentCard
    global malusPlayer
    global playersOrder
    global currentPlayerIndex
    global oneCardPlayer
    if card["card"] in ["colorChange", "+4"]:#Si la carte est une carte sans couleur
        cardCopy = card.copy()
        cardCopy["color"] = None
        playersDeck[player].remove(cardCopy)
    else:
        playersDeck[player].remove(card)
    currentCard = card
    console.print("[italic] " + getPseudo(player) + "[/italic] played the card " + getStringFromCard(card) + "\n")
    if card["card"] == "pass":
        increasePlayerIndex()
    if card["card"] == "+2":
        placerIndex = playersOrder.index(player)
        otherPlayerIndex = placerIndex + 1
        if otherPlayerIndex >= len(playersOrder):
            otherPlayerIndex = 0
        malusPlayer = playersOrder[otherPlayerIndex]
        if str((myIPAddr, multicast_port_me)) == malusPlayer:  # if i'm the player that take the malus
            s.sendto(json.dumps({"api": "askMalus", "cardsNumber": "2"}).encode(),
                     (multicast_group, multicast_port_other))
        while malusPlayer != None:
            continue
    if card["card"] == "+4":
        placerIndex = playersOrder.index(player)
        otherPlayerIndex = placerIndex + 1
        if otherPlayerIndex >= len(playersOrder):
            otherPlayerIndex = 0
        malusPlayer = playersOrder[otherPlayerIndex]
        if str((myIPAddr, multicast_port_me)) == malusPlayer:  # if i'm the player that take the malus
            s.sendto(json.dumps({"api": "askMalus", "cardsNumber": "4"}).encode(),
                     (multicast_group, multicast_port_other))
        while malusPlayer != None:
            continue
    if card["card"] == "invert":
        reversed(playersOrder)
        currentPlayerIndex = len(playersOrder) - currentPlayerIndex - 1
    if len(playersDeck[playersOrder[currentPlayerIndex]]) == 1:#if the current player only have one card left
        oneCardPlayer = True
        console.print("[italic] " + getPseudo(playersOrder[currentPlayerIndex]) + "[/italic] only has 1 card left\n")
        while oneCardPlayer:
            console.print("[bold] ❓ What do you have to say to him? |'uno' or 'contre uno'|[/bold]")
            choice = input(" >> ")
            if choice == "uno" and str((myIPAddr, multicast_port_me)) == playersOrder[currentPlayerIndex]:
                oneCardPlayer = False
                s.sendto(json.dumps({"api": "contreUno", "data": choice}).encode(),
                         (multicast_group, multicast_port_other))
                continue
            elif (choice == "contre uno" and str((myIPAddr, multicast_port_me)) != playersOrder[
                currentPlayerIndex]):  # if the player who counter is not the one who have only one card
                malusPlayer = playersOrder[currentPlayerIndex]
                oneCardPlayer = False
                s.sendto(json.dumps({"api": "contreUno", "data": choice}).encode(),
                         (multicast_group, multicast_port_other))
        while malusPlayer != None:
            continue
    increasePlayerIndex()


def printPlayerDeck():
    """
    Affiche les cartes du joueur dans le terminal
    """
    console.print("[bold] ℹ️ Here are all your cards, choose the card you want to play:\n")
    cards = playersDeck[str((myIPAddr, multicast_port_me))]
    placable_cards = getPlacableCard(cards)
    for i in range(len(placable_cards)):
        console.print(str(i + 1) + ". " + getStringFromCard(placable_cards[i]))
    for card in cards:
        if card not in placable_cards:
            console.print("   " + getStringFromCard(card))
    console.print("\n")


def getPlayerInput(max):
    """
    Affiche le prompt pour demander de choisir une carte
    :param max: Le nombre maximal du choix.
    :return: La carte choisie
    """
    console.print("[bold] ➡️ Your choice |1.." + str(max) + "|: [/bold]")
    choice_card = input(" >> ")
    if not choice_card.isnumeric():
        console.print("[bold] ❌ Wrong choice, please try again")
        return getPlayerInput(max)
    if int(choice_card) <= 0 or int(choice_card) > max:
        console.print("[bold] ❌ Wrong choice, please try again")
        return getPlayerInput(max)
    return choice_card


def getPlayerCardChoice():
    """
    Récupère le choix du joueur et envoi le choix aux autres
    :return: La carte choisie
    """
    global playerThatShouldPioche
    if canPlayerPlay(playersOrder[currentPlayerIndex]):
        printPlayerDeck()
        choice = getPlayerInput(len(getPlacableCard(playersDeck[playersOrder[currentPlayerIndex]])))
        print("")
        card = getPlacableCard(playersDeck[playersOrder[currentPlayerIndex]])[int(choice) - 1].copy()
        if getPlacableCard(playersDeck[playersOrder[currentPlayerIndex]])[int(choice) - 1]["color"] is None:
            console.print(
                "[bold] ➡️ You have to choose the color:[/bold] [#ff0000]1[/#ff0000] - [#00ff00]2[/#00ff00] - [#0000ff]3[/#0000ff] - [#ffff00]4[/#ffff00]")
            colorChoice = getPlayerInput(len(color))
            card["color"] = color[int(colorChoice) - 1]
        return card
    else:
        console.print("[bold] You can't put any cards down, so you have to draw")
        playerThatShouldPioche = str((myIPAddr, multicast_port_me))
        s.sendto(json.dumps({"api": "askPioche"}).encode(), (multicast_group, multicast_port_other))
        while playerThatShouldPioche != None:
            continue
        return None


def getStringFromCard(jsonCard):
    """
    Renvoie une carte sous forme de chaine de caractères.
    :param jsonCard: Une carte sous le format JSON
    :return: String
    """
    if jsonCard["color"] is not None:
        c = ""
        if jsonCard["color"] == "red":
            c = "#ff0000"
        elif jsonCard["color"] == "yellow":
            c = "#ffff00"
        elif jsonCard["color"] == "blue":
            c = "#0000ff"
        elif jsonCard["color"] == "green":
            c = "#00ff00"
        return "[bold " + c + "]" + "< " + jsonCard["card"] + " >" + "[/bold " + c + "]"
    return "[bold] < " + jsonCard["card"] + " > [/bold]"


def chooseFirstCard():
    """
    Choisi la première carte du jeu affiché
    """
    global currentCard
    choice = getARandomCard()
    s.sendto(json.dumps({"api": "firstCard", "data": choice}).encode(), (multicast_group, multicast_port_other))
    currentCard = choice


def getPlacableCard(cards):
    """
    Permet de sélectionner toutes les cartes jouables actuellement.
    :param cards: La liste de toutes les cartes.
    :return: Les cartes jouables.
    """
    result = []
    for card in cards:
        if str(card["color"]) == "None":
            result.append(card)
        elif card["color"] == currentCard["color"]:
            result.append(card)
        elif card["card"] == currentCard["card"]:
            result.append(card)
    return result


def getARandomCard():
    """
    Choisir une carte aléatoirement en fonction des probabilités
    :return: Une carte
    """
    result = {"card": random.choice(cardsChoice), "color": random.choice(color)}
    while result["card"] in ["colorChange", "+4"]:
        result = {"card": random.choice(cardsChoice), "color": random.choice(color)}
    return result


def canPlayerPlay(player):
    """
    Détermine si un joueur peut jouer
    :param player: Le joueur
    :return: Bool
    """
    return len(getPlacableCard(playersDeck[player])) > 0


def pioche(player, card):
    """
    Permet de piocher une carte et de l'afficher au joueur
    :param player: Le joueur
    :param card: La carte choisie par les autres
    """
    global playerThatShouldPioche
    playersDeck[playerThatShouldPioche].append(card)
    if playerThatShouldPioche == str((myIPAddr, multicast_port_me)):
        console.print("[bold] You have drawn the card: [/bold]", getStringFromCard(card))
    else:
        console.print("[italic] " + getPseudo(player) + "[/italic]" + " has picked")
    print("")
    playerThatShouldPioche = None
    increasePlayerIndex()


def malusPioche(player, cards):
    """
    Permet de gérer les cartes avec de mauls qui déclenche une pioche.
    :param player: Le joueur.
    :param cards: Les cartes piochées.
    """
    global malusPlayer
    for card in cards:
        playersDeck[player].append(card)
        if player == str((myIPAddr, multicast_port_me)):
            console.print("[bold] You have picked [/bold]" + getStringFromCard(card))
        else:
            console.print("[italic] " + getPseudo(player) + "[/italic]" + " has picked one card")
    print("")
    malusPlayer = None


def amIThePlayerThatChooseCard(otherPlayer):
    """
    Permet de savoir si le joueur est celui qui doit jouer.
    :param otherPlayer: La liste des joueurs.
    :return: Bool
    """
    otherPlayerIndex = playersOrder.index(otherPlayer)
    myIndex = playersOrder.index(str((myIPAddr, multicast_port_me)))
    otherPlayerIndex += 1
    if otherPlayerIndex >= len(playersOrder):
        otherPlayerIndex = 0
    return myIndex == otherPlayerIndex


def askPseudo():
    """
    Permet de demander le pseudo du joueur.
    :return: Le pseudo.
    """
    # UI
    def ui(error):
        console.clear()
        console.print(
            "[red]  _____      _       _    _             \n |  __ \    | |     | |  | |            \n | |__) |__ | |_   _| |  | |_ __   ___  \n |  ___/ _ \| | | | | |  | | '_ \ / _ \ \n | |  | (_) | | |_| | |__| | | | | (_) |\n |_|   \___/|_|\__, |\____/|_| |_|\___/ \n                __/ |                   \n               |___/                    ")
        console.print("\n\n")
        if error is True:
            console.print("[red]Error")
            console.print("\n")
        console.print("[bold]Enter your name : [/bold]")
        c = input(">> ")
        return c

    choice = ui(False)
    allPseudo = []
    for pseudo in playersPseudo:
        allPseudo.append(playersPseudo[pseudo])
    while choice == "" or choice in allPseudo:
        choice = ui(True)
    s.sendto(json.dumps({"api": "pseudo", "data": choice}).encode(), (multicast_group, multicast_port_other))
    playersPseudo[str((myIPAddr, multicast_port_me))] = choice


def getPseudo(addr):
    """
    Renvoie le pseudo lié à l'adresse
    :param addr: L'adresse du joueur
    :return: Son pseudo
    """
    return playersPseudo[addr]


currentPlayerIndex = 0

# Lancement du jeu avec les différentes étapes
askPseudo()
x = threading.Thread(target=listen)
x.start()
sleep(0.1)
reportPresence()
waitingRoom()

# Choix des cartes des autres joueurs
defineOtherPlayerDeck()
if str((myIPAddr, multicast_port_me)) == playersOrder[len(playersOrder) - 1]:
    chooseFirstCard()
while currentCard is None:
    continue
# Lance la partie et attend qu'elle se termine.
while not isGameFinished():
    if playersOrder[currentPlayerIndex] == str((myIPAddr, multicast_port_me)):
        choice = getPlayerCardChoice()
        if choice is not None:
            s.sendto(json.dumps({"api": "play", "data": {"card": choice}}).encode(),
                     (multicast_group, multicast_port_other))
            placeCard(str((myIPAddr, multicast_port_me)), choice)
console.print(Markdown("# 🎉 The game is over! 🎉"))
