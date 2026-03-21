# clients/claude/supervisor.py
from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clients.claude.config import DaemonConfig
    from clients.claude.irc_connection import IRCConnection
    from clients.claude.webhook import WebhookClient

logger = logging.getLogger(__name__)

CHECK_INTERVAL = 30.0
MIN_EVENTS_FOR_CHECK = 5
MAX_WHISPERS_BEFORE_ESCALATE = 3


class SupervisorAgent:
    """Background supervisor that detects spiraling/stall and intervenes."""

    def __init__(
        self,
        session_id: str,
        channel: str,
        irc: IRCConnection,
        webhooks: WebhookClient,
        config: DaemonConfig,
    ):
        self._session_id = session_id
        self._channel = channel
        self._irc = irc
        self._webhooks = webhooks
        self._config = config
        self._window: deque[dict] = deque(maxlen=20)
        self._whisper_count = 0
        self._task: asyncio.Task | None = None
        self._anthropic_client = None  # lazy-init, reused across evaluations
        # Injector set by SessionManager after spawn
        self._inject_fn = None

    def set_inject_fn(self, fn) -> None:
        self._inject_fn = fn

    def observe(self, event: dict) -> None:
        self._window.append(event)

    async def start(self) -> None:
        self._task = asyncio.create_task(self._check_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _check_loop(self) -> None:
        while True:
            await asyncio.sleep(CHECK_INTERVAL)
            if len(self._window) >= MIN_EVENTS_FOR_CHECK:
                await self._evaluate()

    async def _evaluate(self) -> None:
        if self._anthropic_client is None:
            try:
                import anthropic
            except ImportError:
                logger.warning("anthropic package not installed; supervisor disabled")
                return
            self._anthropic_client = anthropic.AsyncAnthropic()

        events = list(self._window)
        prompt = (
            "You are monitoring an AI agent IRC session. "
            "Review the recent events and decide if intervention is needed.\n\n"
            "Recent events (newest last):\n"
            + json.dumps(events, indent=2)
            + "\n\nRespond with JSON only: "
            '{"status": "ok"} or {"status": "intervene", "message": "reason"}'
        )

        try:
            response = await self._anthropic_client.messages.create(
                model=self._config.supervisor_model,
                max_tokens=128,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            result = json.loads(raw)
            if result.get("status") == "intervene":
                await self._whisper(result.get("message", "Please reconsider your approach."))
        except Exception:
            logger.exception("Supervisor evaluation failed")

    async def _whisper(self, message: str) -> None:
        self._whisper_count += 1
        text = f"[SUPERVISOR] {message}"
        if self._inject_fn:
            await self._inject_fn(text)
        if self._whisper_count >= MAX_WHISPERS_BEFORE_ESCALATE:
            await self._escalate(message)

    async def _escalate(self, message: str) -> None:
        logger.warning("Supervisor escalating session %s: %s", self._session_id, message)
        await self._irc.send_privmsg(
            self._channel,
            f"[SUPERVISOR ESCALATION] Session {self._session_id} may be stuck: {message}",
        )
        await self._webhooks.post(
            self._config.webhooks.on_spiraling,
            {
                "session_id": self._session_id,
                "channel": self._channel,
                "message": message,
            },
        )
