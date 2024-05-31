from textual.message import Message


class Network(Message):
    def __init__(self, addr, data: str) -> None:
        self.data = data
        self.addr = addr
        super().__init__()
