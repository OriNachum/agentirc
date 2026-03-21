# clients/claude/ipc_server.py
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clients.claude.session_manager import SessionManager
    from clients.claude.irc_connection import IRCConnection

logger = logging.getLogger(__name__)


class IPCServer:
    """Unix socket server — agents connect here to call irc_send/irc_read/irc_ask."""

    def __init__(self, socket_path: str, irc: IRCConnection, session_mgr: SessionManager):
        self._socket_path = socket_path
        self._irc = irc
        self._session_mgr = session_mgr
        self._server = None

    async def start(self) -> None:
        if os.path.exists(self._socket_path):
            os.unlink(self._socket_path)
        self._server = await asyncio.start_unix_server(
            self._handle_connection, path=self._socket_path
        )
        os.chmod(self._socket_path, 0o600)
        logger.info("IPC server listening at %s", self._socket_path)

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        if os.path.exists(self._socket_path):
            try:
                os.unlink(self._socket_path)
            except OSError:
                pass

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                try:
                    req = json.loads(line.decode())
                except json.JSONDecodeError:
                    await self._send(writer, {"type": "error", "message": "invalid JSON"})
                    continue
                await self._dispatch(req, writer)
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()

    async def _send(self, writer: asyncio.StreamWriter, obj: dict) -> None:
        try:
            writer.write(json.dumps(obj).encode() + b"\n")
            await writer.drain()
        except (ConnectionError, BrokenPipeError):
            pass

    async def _dispatch(self, req: dict, writer: asyncio.StreamWriter) -> None:
        req_type = req.get("type")
        cid = req.get("correlation_id", "")
        session_id = req.get("session_id", "")

        if req_type == "send":
            channel = req.get("channel", "")
            text = req.get("text", "")
            await self._irc.send_privmsg(channel, text)
            await self._send(writer, {"type": "ack", "correlation_id": cid})

        elif req_type == "read":
            channel = req.get("channel", "")
            limit = req.get("limit", 20)
            messages = await self._fetch_history(channel, limit)
            await self._send(writer, {
                "type": "history",
                "correlation_id": cid,
                "messages": messages,
            })

        elif req_type == "ask":
            channel = req.get("channel", "")
            question = req.get("question", "")
            timeout = req.get("timeout", 120)
            session = self._session_mgr.get_session(session_id)
            if session is None:
                await self._send(writer, {
                    "type": "error",
                    "correlation_id": cid,
                    "message": "unknown session",
                })
                return
            fut: asyncio.Future = asyncio.get_running_loop().create_future()
            session.pending_questions[cid] = fut
            # Start question flow in background; respond when future resolves
            asyncio.create_task(
                self._session_mgr.question_flow.ask(channel, question, cid, fut, timeout)
            )
            try:
                answer = await asyncio.wait_for(asyncio.shield(fut), timeout=timeout + 5)
                await self._send(writer, {
                    "type": "reply",
                    "correlation_id": cid,
                    "answer": answer,
                })
            except (asyncio.TimeoutError, TimeoutError):
                await self._send(writer, {
                    "type": "error",
                    "correlation_id": cid,
                    "message": f"No answer within {timeout + 5}s",
                })
            finally:
                session.pending_questions.pop(cid, None)

        elif req_type == "whisper":
            text = req.get("text", "")
            session = self._session_mgr.get_session(session_id)
            if session:
                await self._session_mgr.inject_supervisor_whisper(session_id, text)
            await self._send(writer, {"type": "ack", "correlation_id": cid})

        else:
            await self._send(writer, {
                "type": "error",
                "correlation_id": cid,
                "message": f"unknown type: {req_type}",
            })

    async def _fetch_history(self, channel: str, limit: int) -> list[dict]:
        """Ask the IRCd for recent history via HISTORY RECENT."""
        messages: list[dict] = []
        # We need to send the command and collect the replies.
        # Use a temporary future/queue to collect HISTORY replies.
        q: asyncio.Queue = asyncio.Queue()

        async def _collector(msg):
            from protocol.message import Message as IRCMsg
            if msg.command == "HISTORY" and msg.params and msg.params[0] == channel:
                # :server HISTORY <channel> <nick> <ts> :<text>
                if len(msg.params) >= 4:
                    q.put_nowait({
                        "nick": msg.params[1],
                        "ts": msg.params[2],
                        "text": msg.params[3] if len(msg.params) > 3 else "",
                    })
            elif msg.command == "HISTORYEND" and msg.params and msg.params[0] == channel:
                q.put_nowait(None)  # sentinel

        self._irc.add_handler(_collector)
        try:
            await self._irc.send_raw(f"HISTORY RECENT {channel} {limit}")
            # Collect until sentinel or timeout
            loop = asyncio.get_running_loop()
            deadline = loop.time() + 5.0
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    break
                try:
                    item = await asyncio.wait_for(q.get(), timeout=remaining)
                    if item is None:
                        break
                    messages.append(item)
                except asyncio.TimeoutError:
                    break
        finally:
            self._irc.remove_handler(_collector)

        return messages
