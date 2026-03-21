# clients/claude/irc_connection.py
from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable

from protocol.message import Message

logger = logging.getLogger(__name__)

MAX_CHUNK = 400  # stay well under 512-byte IRC line limit


class IRCConnection:
    """Persistent IRC client with auto-reconnect."""

    def __init__(self, host: str, port: int, nick: str, user: str, realname: str):
        self.host = host
        self.port = port
        self.nick = nick
        self.user = user
        self.realname = realname

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = asyncio.Event()
        self._handlers: list[Callable[[Message], Awaitable[None]]] = []
        self._running = False

    def add_handler(self, fn: Callable[[Message], Awaitable[None]]) -> None:
        self._handlers.append(fn)

    async def wait_connected(self) -> None:
        await self._connected.wait()

    async def run(self) -> None:
        """Reconnect loop with exponential backoff."""
        self._running = True
        delay = 1.0
        while self._running:
            try:
                await self._connect()
                delay = 1.0
                await self._read_loop()
            except Exception as exc:
                logger.warning("IRC connection lost: %s — reconnecting in %.0fs", exc, delay)
            finally:
                self._connected.clear()
                if self._writer:
                    try:
                        self._writer.close()
                    except Exception:
                        pass
                    self._writer = None
                    self._reader = None
            if self._running:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60.0)

    async def _connect(self) -> None:
        self._reader, self._writer = await asyncio.open_connection(self.host, self.port)
        await self._send_raw(f"NICK {self.nick}")
        await self._send_raw(f"USER {self.user} 0 * :{self.realname}")

    async def _read_loop(self) -> None:
        buffer = ""
        while True:
            assert self._reader is not None
            data = await self._reader.read(4096)
            if not data:
                break
            buffer += data.decode("utf-8", errors="replace")
            buffer = buffer.replace("\r\n", "\n").replace("\r", "\n")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if not line.strip():
                    continue
                msg = Message.parse(line)
                if not msg.command:
                    continue
                # Handle PING inline
                if msg.command == "PING":
                    token = msg.params[0] if msg.params else ""
                    await self._send_raw(f"PONG :{token}")
                    continue
                # Mark as connected on 001 welcome
                if msg.command == "001":
                    self._connected.set()
                await self._dispatch(msg)

    def remove_handler(self, fn: Callable[[Message], Awaitable[None]]) -> None:
        try:
            self._handlers.remove(fn)
        except ValueError:
            pass

    async def _dispatch(self, msg: Message) -> None:
        for handler in list(self._handlers):  # snapshot to allow mutation during dispatch
            try:
                await handler(msg)
            except Exception:
                logger.exception("IRC handler error on %s", msg.command)

    async def _send_raw(self, line: str) -> None:
        if self._writer is None:
            return
        try:
            self._writer.write(f"{line}\r\n".encode("utf-8"))
            await self._writer.drain()
        except (ConnectionError, BrokenPipeError, OSError):
            pass

    async def send_privmsg(self, target: str, text: str) -> None:
        """Send PRIVMSG, chunking long messages to stay under 512 bytes."""
        await self.wait_connected()
        for i in range(0, max(len(text), 1), MAX_CHUNK):
            chunk = text[i:i + MAX_CHUNK]
            await self._send_raw(f"PRIVMSG {target} :{chunk}")

    async def join(self, channel: str) -> None:
        await self.wait_connected()
        await self._send_raw(f"JOIN {channel}")

    async def send_raw(self, line: str) -> None:
        await self.wait_connected()
        await self._send_raw(line)

    async def stop(self) -> None:
        self._running = False
        self._connected.clear()
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
