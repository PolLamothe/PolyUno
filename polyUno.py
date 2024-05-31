from textual.app import App, ComposeResult
from textual.message import Message
from textual.widgets import Static, DataTable, Header, Button, Input, Label, Footer
from textual.containers import Grid, Vertical, Horizontal, Container

from UI.NameScreen import NameScreen
from UI.NetworkMessage import Network
from UI.WaitingRoom import WaitingRoom
from game2 import Game


class PolyUno(App):
    CSS_PATH = "UI/UI.tcss"
    BINDINGS = [("q", "quit", "Quit game")]

    def __init__(self, g):
        super().__init__()
        self.game = g

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(id="screen")
        yield Footer()

    async def on_mount(self):
        self.game.start_network(self.network_event)
        self.show_name_screen()

    def network_event(self, addr, data):
        self.post_message(Network(addr, data))

    def action_quit(self):
        exit(0)

    def show_new_content(self, c):
        screen = self.query_one("#screen", Vertical)
        screen.remove_children("*")
        screen.mount(c)

    def show_name_screen(self):
        name_screen = NameScreen(self.game)
        self.show_new_content(name_screen)

    def show_waiting_screen(self):
        waiting_screen = WaitingRoom(self.game)
        self.show_new_content(waiting_screen)

    def on_name_screen_changed(self, message: NameScreen.Changed) -> None:
        self.show_waiting_screen()

# ----------
# Start game
# ----------


if __name__ == "__main__":
    game = Game()
    app = PolyUno(game)
    app.run()
