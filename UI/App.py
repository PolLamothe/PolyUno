from textual.app import App, ComposeResult
from textual.widgets import Static, DataTable, Header, Button, Input, Label, Footer
from textual.containers import Grid, Vertical, Horizontal

from NameScreen import NameScreen
from WaitingRoom import WaitingRoom


class PolyUno(App):
    CSS_PATH = "UI.tcss"
    BINDINGS = [("q", "quit", "Quit game")]

    def __init__(self):
        super().__init__()
        self.view = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            NameScreen(),
            id="screen"
        )
        yield Footer()

    def action_quit(self):
        exit(0)

    def show_new_content(self, name: str):
        screen = self.query_one("#screen", Vertical)
        screen.remove_children("*")
        screen.mount(WaitingRoom())


if __name__ == "__main__":
    app = PolyUno()
    app.run()
