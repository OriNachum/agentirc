# clients/claude/daemon.py
from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING

from protocol.message import Message
from clients.claude.irc_connection import IRCConnection
from clients.claude.session_manager import SessionManager
from clients.claude.ipc_server import IPCServer
from clients.claude.question_flow import QuestionFlow
from clients.claude.webhook import WebhookClient

if TYPE_CHECKING:
    from clients.claude.config import DaemonConfig

logger = logging.getLogger(__name__)

# Matches "@nick rest-of-message"
_MENTION_RE = re.compile(r"^@(\S+)\s+(.*)", re.DOTALL)


class ClaudeDaemon:
    """Top-level orchestrator: IRC ↔ SessionManager ↔ IPC."""

    def __init__(self, config: DaemonConfig):
        self._config = config
        self._nick = f"{config.server_name}-{config.agent_name}"

        self._irc = IRCConnection(
            host=config.irc_host,
            port=config.irc_port,
            nick=self._nick,
            user=config.agent_name,
            realname=f"{config.agent_name} agent on {config.server_name}",
        )
        self._webhooks = WebhookClient()
        self._question_flow = QuestionFlow(self._irc, self._webhooks, config)
        self._session_mgr = SessionManager(config, self._irc, self._question_flow, self._webhooks)
        self._ipc = IPCServer(config.ipc_socket, self._irc, self._session_mgr)

    async def run(self) -> None:
        self._irc.add_handler(self._on_irc_message)

        await self._ipc.start()

        # Run IRC reconnect loop in background; _join_channels is called on each 001
        irc_task = asyncio.create_task(self._irc.run())

        try:
            await irc_task
        finally:
            await self._ipc.stop()
            await self._session_mgr.stop_all()
            await self._webhooks.close()

    async def _join_channels(self) -> None:
        await self._irc.wait_connected()
        for channel in self._config.channels:
            await self._irc.join(channel)
            logger.info("Joined %s as %s", channel, self._nick)

    async def _on_irc_message(self, msg: Message) -> None:
        # Re-join channels on every successful registration (reconnect support)
        if msg.command == "001":
            asyncio.create_task(self._join_channels())
            return

        if msg.command != "PRIVMSG":
            return
        if not msg.params or len(msg.params) < 2:
            return

        target = msg.params[0]
        text = msg.params[1]
        sender_nick = msg.prefix.split("!")[0] if msg.prefix else ""

        # Ignore our own messages
        if sender_nick == self._nick:
            return

        # Determine if DM or channel message
        is_dm = not target.startswith("#")
        channel = None if is_dm else target

        if is_dm:
            # DM addressed directly to us
            await self._handle_trigger_or_answer(sender_nick, None, text)
            return

        # Channel message — check for @mention
        m = _MENTION_RE.match(text)
        if m:
            mentioned_nick = m.group(1)
            rest = m.group(2)
            if mentioned_nick == self._nick:
                # It's addressed to us
                await self._handle_trigger_or_answer(sender_nick, channel, rest)

    async def _handle_trigger_or_answer(
        self, nick: str, channel: str | None, text: str
    ) -> None:
        """Check if this message resolves a pending question; otherwise trigger session."""
        active = self._session_mgr.active_session
        if active and active.pending_questions:
            # Route to first pending question (simple FIFO)
            cid = next(iter(active.pending_questions))
            if self._is_trusted(nick):
                await self._session_mgr.resolve_question(active.id, cid, text)
                return

        await self._session_mgr.handle_trigger(nick, channel, text)

    def _is_trusted(self, nick: str) -> bool:
        """Humans are always trusted; agent trust follows config policy.

        On this network ALL nicks follow <server>-<agent> format (protocol
        invariant), so `is_agent` is always True — meaning both humans and
        agents are governed by the `trust.agents` policy (default: "vote" →
        trusted).  The distinction between human and agent is intentionally not
        encoded in the nick format; trust is policy-driven.
        """
        agent_pattern = re.compile(r"^\w+-\w+$")
        is_agent = bool(agent_pattern.match(nick)) and "-" in nick
        if not is_agent:
            return True  # human (non-conforming nick, e.g. in tests)
        policy = self._config.trust.agents
        if policy == "never":
            return False
        if policy in ("first", "vote", "consensus"):
            return True  # simplified: trust agents per policy
        return False
