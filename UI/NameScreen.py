from textual import events
from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal, Center
from textual.css.query import QueryError
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Label, Input, Button


class NameScreen(Container):
    class Changed(Message):
        def __init__(self, name: str) -> None:
            self.name = name
            super().__init__()

    def __init__(self, game):
        super().__init__()
        self.game = game

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("  _____      _       _    _             \n |  __ \    | |     | |  | |            \n | |__) |__ | |_   _| |  | |_ __   ___  \n |  ___/ _ \| | | | | |  | | '_ \ / _ \ \n | |  | (_) | | |_| | |__| | | | | (_) |\n |_|   \___/|_|\__, |\____/|_| |_|\___/ \n                __/ |                   \n               |___/                    ", classes="name-title"),
            Label("Enter your name : ", classes="label-name"),
            Input(placeholder="Name", max_length=20, classes="input-name", id="name-input"),
            Horizontal(
                Button("Join", variant="primary", id="join-button"),
                classes="center-h name-btn-c"
            ),
            classes="name-container"
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "join-button":
            # Get the input value
            input_name = self.query_one("#name-input", Input)
            name = input_name.value

            # Validate the input
            if not name.strip():
                self.app.notify("Your name cannot be empty !", title="Error :", severity="error")
            elif not self.game.set_pseudo(name):
                self.app.notify("Your name has already been taken", title="Error :", severity="error")
            else:
                self.post_message(self.Changed(name))
