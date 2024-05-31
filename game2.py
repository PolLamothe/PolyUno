import argparse
import threading

from NetworkSocket import NetworkSocket


class Game:
    ALLCARDS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "invert", "+2", "+4", "colorChange", "pass"]
    COLORS = ["red", "green", "blue", "yellow"]

    def __init__(self):
        # To debug start an instance with -debug-server True and another with -debug-client True
        parser = argparse.ArgumentParser()
        parser.add_argument("-debug-server", dest="debug_server", action='store_true')
        parser.add_argument("-debug-client", dest="debug_client", action='store_true')
        parser.add_argument("-debug", dest="debug", action='store_true')
        self.args = parser.parse_args()

        # Globals vars
        self.playersOrder = []
        self.playersDeck = {}
        self.currentCard = None
        self.playerThatShouldPioche = None
        self.malusPlayer = None
        self.oneCardPlayer = False
        self.game_started = False

        # Socket
        self.s = NetworkSocket(self.args)

    def start_network(self, event):
        if self.args.debug:
            print("Debug --> Starting network...")
        t = threading.Thread(target=self.s.listen, args=(event,))
        t.start()

    def set_pseudo(self, name):
        # Défini le pseudo return True si possible False sinon
        all_pseudo = []
        for pseudo in self.s.playersPseudo:
            all_pseudo.append(self.s.playersPseudo[pseudo])
        if name == "" or name in all_pseudo:
            return False
        self.s.send_pseudo(name)
        return True

    def get_pseudo(self, addr):
        return self.s.playersPseudo[addr]

    def get_all_players(self):
        all_players = []
        for el in self.s.allPlayersIp:
            r = "✅" if self.s.is_ready(el) else "❌"
            all_players.append((self.s.playersPseudo[el], el, r))
        return all_players

    def set_game_state(self, state):
        self.game_started = state
        self.s.discover_player = state
