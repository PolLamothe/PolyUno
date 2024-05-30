from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal, Center
from textual.css.query import QueryError
from textual.widgets import Label, Input, Button, DataTable


class WaitingRoom(Container):
    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Waiting for players..."),
            DataTable(classes="waiting-table"),
            classes="center-h"
        )

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Name", "IP", "Ready")
        table.add_rows([("Test1", "192.168.1.1", "❌"), ("Test2", "192.168.1.2", "✅")])
