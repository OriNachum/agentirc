# clients/claude/session_manager.py
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clients.claude.config import DaemonConfig
    from clients.claude.irc_connection import IRCConnection
    from clients.claude.supervisor import SupervisorAgent
    from clients.claude.question_flow import QuestionFlow
    from clients.claude.webhook import WebhookClient

logger = logging.getLogger(__name__)

INITIAL_PROMPT_TEMPLATE = """\
You are {nick}, an AI agent on the agentirc IRC mesh.

Your IRC skills are available via the agentirc skill (scripts in $AGENTIRC_SKILL_DIR):
  python irc.py send '<channel>' '<message>'      # post a message to a channel
  python irc.py read '<channel>' --limit N        # fetch recent history
  python irc.py ask  '<channel>' '<question>' [--timeout N]  # block for a human/agent answer

Environment:
  AGENTIRC_SOCKET={socket}
  AGENTIRC_SESSION_ID={session_id}
  AGENTIRC_NICK={nick}
  AGENTIRC_CHANNEL={channel}

You were triggered by {trigger_nick} in {trigger_location}:
  {trigger_text}

Respond in the channel (or via DM if triggered by a DM). Be helpful and concise.
"""


@dataclass
class Session:
    id: str
    trigger_nick: str
    trigger_channel: str | None
    proc: asyncio.subprocess.Process
    supervisor: SupervisorAgent
    pending_questions: dict[str, asyncio.Future] = field(default_factory=dict)


class SessionManager:
    """Spawns and routes Claude CLI sessions."""

    def __init__(
        self,
        config: DaemonConfig,
        irc: IRCConnection,
        question_flow: QuestionFlow,
        webhooks: WebhookClient,
    ):
        self._config = config
        self._irc = irc
        self.question_flow = question_flow
        self._webhooks = webhooks
        self._sessions: dict[str, Session] = {}
        self._active_session_id: str | None = None

    def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    @property
    def active_session(self) -> Session | None:
        if self._active_session_id:
            return self._sessions.get(self._active_session_id)
        return None

    async def handle_trigger(
        self, nick: str, channel: str | None, text: str
    ) -> None:
        """Entry point for @mentions and DMs."""
        if self._active_session_id and self._active_session_id in self._sessions:
            await self._inject_message(
                self._sessions[self._active_session_id], nick, channel, text
            )
        else:
            await self._spawn_session(nick, channel, text)

    async def _spawn_session(
        self, nick: str, channel: str | None, text: str
    ) -> None:
        from clients.claude.supervisor import SupervisorAgent

        session_id = str(uuid.uuid4())
        trigger_location = channel or f"DM from {nick}"

        initial_prompt = INITIAL_PROMPT_TEMPLATE.format(
            nick=self._irc.nick,
            socket=self._config.ipc_socket,
            session_id=session_id,
            channel=channel or "",
            trigger_nick=nick,
            trigger_location=trigger_location,
            trigger_text=text,
        )

        env = {
            **os.environ,
            "AGENTIRC_SOCKET": self._config.ipc_socket,
            "AGENTIRC_SESSION_ID": session_id,
            "AGENTIRC_NICK": self._irc.nick,
            "AGENTIRC_CHANNEL": channel or "",
        }

        try:
            proc = await asyncio.create_subprocess_exec(
                "claude",
                "--print",
                "--output-format", "stream-json",
                "--input-format", "stream-json",
                "--dangerously-skip-permissions",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                cwd=self._config.working_dir,
                env=env,
            )
        except FileNotFoundError:
            logger.error("'claude' CLI not found — cannot spawn session")
            if channel:
                await self._irc.send_privmsg(
                    channel, f"[ERROR] claude CLI not found; cannot start session"
                )
            return

        supervisor = SupervisorAgent(
            session_id=session_id,
            channel=channel or self._config.channels[0],
            irc=self._irc,
            webhooks=self._webhooks,
            config=self._config,
        )

        session = Session(
            id=session_id,
            trigger_nick=nick,
            trigger_channel=channel,
            proc=proc,
            supervisor=supervisor,
        )
        supervisor.set_inject_fn(
            lambda text: self.inject_supervisor_whisper(session_id, text)
        )

        self._sessions[session_id] = session
        self._active_session_id = session_id

        await supervisor.start()

        # Send initial prompt as stream-json
        initial_payload = json.dumps({"type": "user", "message": {"role": "user", "content": initial_prompt}})
        assert proc.stdin is not None
        proc.stdin.write(initial_payload.encode() + b"\n")
        await proc.stdin.drain()

        asyncio.create_task(self._drain_session_output(session))
        logger.info("Spawned session %s triggered by %s", session_id, nick)

    async def _inject_message(
        self, session: Session, nick: str, channel: str | None, text: str
    ) -> None:
        payload = json.dumps({
            "type": "user",
            "message": {
                "role": "user",
                "content": f"[{nick} in {channel or 'DM'}]: {text}",
            },
        })
        if session.proc.stdin:
            session.proc.stdin.write(payload.encode() + b"\n")
            try:
                await session.proc.stdin.drain()
            except (ConnectionResetError, BrokenPipeError):
                logger.warning("Session %s stdin closed", session.id)

    async def inject_supervisor_whisper(self, session_id: str, text: str) -> None:
        session = self._sessions.get(session_id)
        if session and session.proc.stdin:
            payload = json.dumps({
                "type": "user",
                "message": {"role": "user", "content": text},
            })
            try:
                session.proc.stdin.write(payload.encode() + b"\n")
                await session.proc.stdin.drain()
            except (ConnectionResetError, BrokenPipeError):
                pass

    async def resolve_question(
        self, session_id: str, correlation_id: str, answer: str
    ) -> None:
        session = self._sessions.get(session_id)
        if session:
            fut = session.pending_questions.get(correlation_id)
            if fut and not fut.done():
                fut.set_result(answer)

    async def _drain_session_output(self, session: Session) -> None:
        assert session.proc.stdout is not None
        try:
            async for line in session.proc.stdout:
                raw = line.decode("utf-8", errors="replace").strip()
                if not raw:
                    continue
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                session.supervisor.observe(event)
                # Forward assistant messages to IRC
                await self._forward_to_irc(session, event)
        except Exception:
            logger.exception("Session %s output drain error", session.id)
        finally:
            await session.proc.wait()
            await session.supervisor.stop()
            if self._active_session_id == session.id:
                self._active_session_id = None
            self._sessions.pop(session.id, None)
            logger.info("Session %s ended", session.id)

    async def _forward_to_irc(self, session: Session, event: dict) -> None:
        """Forward assistant text content to the trigger channel/nick."""
        # stream-json events have type "assistant" with message content
        if event.get("type") != "assistant":
            return
        message = event.get("message", {})
        if not isinstance(message, dict):
            return
        content = message.get("content", [])
        if isinstance(content, str):
            text = content.strip()
        elif isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
            text = " ".join(parts).strip()
        else:
            return
        if not text:
            return
        target = session.trigger_channel or session.trigger_nick
        await self._irc.send_privmsg(target, text)

    async def stop_all(self) -> None:
        for session in list(self._sessions.values()):
            if session.proc.returncode is None:
                session.proc.terminate()
                try:
                    await asyncio.wait_for(session.proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    session.proc.kill()
                    await session.proc.wait()
            await session.supervisor.stop()
        self._sessions.clear()
        self._active_session_id = None
