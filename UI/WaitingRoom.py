from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal, Center
from textual.css.query import QueryError
from textual.widgets import Label, Input, Button, DataTable

from UI.NetworkMessage import Network


class WaitingRoom(Container):
    def __init__(self, game):
        super().__init__()
        self.game = game
        self.players = self.game.get_all_players()
        self.table = DataTable(classes="waiting-table")

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Waiting for players..."),
            self.table,
            classes="center-h"
        )

    def on_mount(self) -> None:
        # Report presence
        self.game.s.report_presence()
        self.table.add_columns("Name", "IP", "Ready")
        self.table.add_rows(self.players)

    def refresh_table(self) -> None:
        self.players = self.game.get_all_players()
        self.table.clear()
        for row in self.players:
            self.table.add_row(*row)
