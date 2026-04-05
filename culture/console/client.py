"""ConsoleIRCClient — persistent IRC client for the console TUI.

Combines the persistent connection pattern of IRCTransport with the query
methods of IRCObserver. Designed for the console TUI: buffers incoming
PRIVMSG messages and provides async query methods for LIST, WHO, and HISTORY.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from culture.protocol.message import Message

logger = logging.getLogger(__name__)

# Timeout for query operations (LIST, WHO, HISTORY)
QUERY_TIMEOUT = 10.0
# Timeout for registration (NICK + USER → 001)
REGISTER_TIMEOUT = 15.0


@dataclass
class ChatMessage:
    """A buffered chat message from a channel or DM."""

    channel: str
    nick: str
    text: str
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class ConsoleIRCClient:
    """Async IRC client for the console TUI.

    Maintains a persistent connection, buffers incoming PRIVMSG messages,
    and provides query methods for channel listing, WHO, and history.
    """

    def __init__(
        self,
        host: str,
        port: int,
        nick: str,
        mode: str = "H",
        icon: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.nick = nick
        self.mode = mode
        self.icon = icon

        self.connected: bool = False
        self.joined_channels: set[str] = set()

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._read_task: asyncio.Task | None = None

        # Buffer for incoming PRIVMSG messages
        self._message_buffer: list[ChatMessage] = []

        # Pending futures for single-response queries (keyed by command string)
        self._pending: dict[str, asyncio.Future[Any]] = {}

        # Accumulation buffers for multi-line query responses
        # keyed by query key (e.g. "LIST", "WHO #chan", "HISTORY #chan")
        self._collect_buffers: dict[str, list[Any]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open TCP connection, register nick, set user mode, send ICON."""
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port),
            timeout=REGISTER_TIMEOUT,
        )

        await self._send_raw(f"NICK {self.nick}")
        await self._send_raw(f"USER {self.nick} 0 * :{self.nick}")

        # Wait for RPL_WELCOME (001) before proceeding
        welcome_future: asyncio.Future[Message] = asyncio.get_event_loop().create_future()
        self._pending["001"] = welcome_future

        # Start the read loop so the future can be resolved
        self._read_task = asyncio.create_task(self._read_loop())

        try:
            await asyncio.wait_for(welcome_future, timeout=REGISTER_TIMEOUT)
        except asyncio.TimeoutError:
            if self._read_task:
                self._read_task.cancel()
            raise ConnectionError("Timed out waiting for server welcome (001)")

        # Set user mode
        if self.mode:
            await self._send_raw(f"MODE {self.nick} +{self.mode}")

        # Send ICON if provided
        if self.icon:
            await self._send_raw(f"ICON {self.icon}")

    async def disconnect(self) -> None:
        """Send QUIT and close the connection."""
        self.connected = False

        if self._read_task:
            self._read_task.cancel()
            await asyncio.gather(self._read_task, return_exceptions=True)
            self._read_task = None

        if self._writer:
            try:
                await self._send_raw("QUIT :console done")
            except (ConnectionError, BrokenPipeError, OSError):
                pass
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except (ConnectionError, BrokenPipeError, OSError):
                pass
            self._writer = None
            self._reader = None

    async def join(self, channel: str) -> None:
        """Join a channel and track it in joined_channels."""
        await self._send_raw(f"JOIN {channel}")
        self.joined_channels.add(channel)

    async def part(self, channel: str) -> None:
        """Part a channel and remove it from joined_channels."""
        await self._send_raw(f"PART {channel}")
        self.joined_channels.discard(channel)

    async def send_privmsg(self, target: str, text: str) -> None:
        """Send a PRIVMSG to a channel or nick."""
        await self._send_raw(f"PRIVMSG {target} :{text}")

    async def send_raw(self, line: str) -> None:
        """Send a raw IRC line. Public interface for custom commands."""
        await self._send_raw(line)

    def drain_messages(self) -> list[ChatMessage]:
        """Return and clear all buffered incoming messages."""
        msgs = list(self._message_buffer)
        self._message_buffer.clear()
        return msgs

    async def list_channels(self) -> list[str]:
        """Send LIST, collect RPL_LIST (322) responses, wait for RPL_LISTEND (323).

        Returns a sorted list of channel names.
        """
        key = "LIST"
        self._collect_buffers[key] = []
        end_future: asyncio.Future[None] = asyncio.get_event_loop().create_future()
        self._pending["323"] = end_future

        await self._send_raw("LIST")

        try:
            await asyncio.wait_for(end_future, timeout=QUERY_TIMEOUT)
        except asyncio.TimeoutError:
            pass
        finally:
            self._pending.pop("323", None)

        channels = list(self._collect_buffers.pop(key, []))
        return sorted(channels)

    async def who(self, target: str) -> list[dict]:
        """Send WHO <target>, collect RPL_WHOREPLY (352) responses, wait for RPL_ENDOFWHO (315).

        Returns a list of dicts with nick, user, host, server, flags, realname.
        """
        key = f"WHO {target}"
        self._collect_buffers[key] = []
        end_future: asyncio.Future[None] = asyncio.get_event_loop().create_future()
        self._pending[f"315:{target}"] = end_future

        await self._send_raw(f"WHO {target}")

        try:
            await asyncio.wait_for(end_future, timeout=QUERY_TIMEOUT)
        except asyncio.TimeoutError:
            pass
        finally:
            self._pending.pop(f"315:{target}", None)

        entries = list(self._collect_buffers.pop(key, []))
        return entries

    async def history(self, channel: str, limit: int = 50) -> list[dict]:
        """Send HISTORY RECENT <channel> <limit>, collect HISTORY responses, wait for HISTORYEND.

        Returns a list of dicts with channel, nick, timestamp, text.
        """
        key = f"HISTORY {channel}"
        self._collect_buffers[key] = []
        end_future: asyncio.Future[None] = asyncio.get_event_loop().create_future()
        self._pending[f"HISTORYEND:{channel}"] = end_future

        await self._send_raw(f"HISTORY RECENT {channel} {limit}")

        try:
            await asyncio.wait_for(end_future, timeout=QUERY_TIMEOUT)
        except asyncio.TimeoutError:
            pass
        finally:
            self._pending.pop(f"HISTORYEND:{channel}", None)

        entries = list(self._collect_buffers.pop(key, []))
        return entries

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _send_raw(self, line: str) -> None:
        """Write a raw IRC line to the socket."""
        if self._writer:
            self._writer.write(f"{line}\r\n".encode())
            await self._writer.drain()

    async def _read_loop(self) -> None:
        """Background task: read lines from socket and dispatch to _handle."""
        buf = ""
        try:
            while True:
                assert self._reader is not None
                data = await self._reader.read(4096)
                if not data:
                    break
                buf += data.decode("utf-8", errors="replace")
                buf = buf.replace("\r\n", "\n").replace("\r", "\n")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    if line.strip():
                        msg = Message.parse(line)
                        await self._handle(msg)
        except asyncio.CancelledError:
            raise
        except (ConnectionError, OSError):
            logger.warning("ConsoleIRCClient: connection lost")
        finally:
            self.connected = False

    async def _handle(self, msg: Message) -> None:
        """Route a parsed IRC message to the appropriate handler."""
        if msg.command == "PING":
            await self._on_ping(msg)

        elif msg.command == "001":
            # RPL_WELCOME — resolve the welcome future
            self.connected = True
            fut = self._pending.pop("001", None)
            if fut and not fut.done():
                fut.set_result(msg)

        elif msg.command == "PRIVMSG":
            self._on_privmsg(msg)

        elif msg.command == "322":
            # RPL_LIST: accumulate channel name
            # params: [our_nick, channel, user_count, :topic]
            if len(msg.params) >= 2:
                channel_name = msg.params[1]
                buf = self._collect_buffers.get("LIST")
                if buf is not None:
                    buf.append(channel_name)

        elif msg.command == "323":
            # RPL_LISTEND
            fut = self._pending.pop("323", None)
            if fut and not fut.done():
                fut.set_result(None)

        elif msg.command == "352":
            # RPL_WHOREPLY:
            # params: [our_nick, target, user, host, server, nick, flags, :realname]
            if len(msg.params) >= 6:
                entry = {
                    "nick": msg.params[5],
                    "user": msg.params[2],
                    "host": msg.params[3],
                    "server": msg.params[4],
                    "flags": msg.params[6] if len(msg.params) > 6 else "",
                    "realname": msg.params[7] if len(msg.params) > 7 else "",
                }
                target = msg.params[1]
                key = f"WHO {target}"
                buf = self._collect_buffers.get(key)
                if buf is not None:
                    buf.append(entry)

        elif msg.command == "315":
            # RPL_ENDOFWHO: params[1] is the target
            target = msg.params[1] if len(msg.params) >= 2 else ""
            fut_key = f"315:{target}"
            fut = self._pending.pop(fut_key, None)
            if fut and not fut.done():
                fut.set_result(None)

        elif msg.command == "HISTORY":
            # HISTORY response: params [channel, nick, timestamp, text]
            if len(msg.params) >= 4:
                channel = msg.params[0]
                entry = {
                    "channel": channel,
                    "nick": msg.params[1],
                    "timestamp": msg.params[2],
                    "text": msg.params[3],
                }
                key = f"HISTORY {channel}"
                buf = self._collect_buffers.get(key)
                if buf is not None:
                    buf.append(entry)

        elif msg.command == "HISTORYEND":
            # HISTORYEND: params[0] is the channel
            channel = msg.params[0] if msg.params else ""
            fut_key = f"HISTORYEND:{channel}"
            fut = self._pending.pop(fut_key, None)
            if fut and not fut.done():
                fut.set_result(None)

    async def _on_ping(self, msg: Message) -> None:
        """Respond to PING with PONG."""
        token = msg.params[0] if msg.params else ""
        await self._send_raw(f"PONG :{token}")

    def _on_privmsg(self, msg: Message) -> None:
        """Buffer an incoming PRIVMSG message."""
        if len(msg.params) < 2:
            return
        target = msg.params[0]
        text = msg.params[1]
        sender = msg.prefix.split("!")[0] if msg.prefix else "unknown"
        if sender == self.nick:
            return  # don't buffer own messages
        channel = target if target.startswith("#") else f"DM:{sender}"
        self._message_buffer.append(ChatMessage(channel=channel, nick=sender, text=text))

    async def _wait_for(self, command: str, timeout: float = QUERY_TIMEOUT) -> Any:
        """Create and await an asyncio.Future for a specific response command.

        Stores the future in self._pending[command] so _handle can resolve it.
        """
        fut: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
        self._pending[command] = fut
        try:
            return await asyncio.wait_for(asyncio.shield(fut), timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(command, None)
            raise
