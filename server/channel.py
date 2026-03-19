from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.client import Client


class Channel:
    """Represents an IRC channel with members and topic."""

    def __init__(self, name: str):
        self.name = name
        self.topic: str | None = None
        self.members: set[Client] = set()

    def add(self, client: Client) -> None:
        self.members.add(client)

    def remove(self, client: Client) -> None:
        self.members.discard(client)
