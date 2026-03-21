#!/usr/bin/env python3
# clients/claude/skill/scripts/irc.py
"""IRC skill CLI — connects to the daemon IPC socket and sends/reads/asks."""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import uuid


def _get_socket_path() -> str:
    path = os.environ.get("AGENTIRC_SOCKET", "")
    if not path:
        sys.exit("ERROR: AGENTIRC_SOCKET not set")
    return path


def _get_session_id() -> str:
    session_id = os.environ.get("AGENTIRC_SESSION_ID", "")
    if not session_id:
        sys.exit("ERROR: AGENTIRC_SESSION_ID not set")
    return session_id


def _send_request(payload: dict, timeout: float = 10.0) -> dict:
    """Send a request to the IPC socket and return the response."""
    sock_path = _get_socket_path()
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(sock_path)
        sock.sendall(json.dumps(payload).encode() + b"\n")
        buf = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf += chunk
            if b"\n" in buf:
                line, _ = buf.split(b"\n", 1)
                return json.loads(line.decode())
    finally:
        sock.close()
    return {}


def cmd_send(args: argparse.Namespace) -> None:
    resp = _send_request({
        "type": "send",
        "session_id": _get_session_id(),
        "channel": args.channel,
        "text": args.text,
        "correlation_id": str(uuid.uuid4()),
    })
    if resp.get("type") == "error":
        sys.exit(f"ERROR: {resp.get('message')}")


def cmd_read(args: argparse.Namespace) -> None:
    resp = _send_request({
        "type": "read",
        "session_id": _get_session_id(),
        "channel": args.channel,
        "limit": args.limit,
        "correlation_id": str(uuid.uuid4()),
    })
    if resp.get("type") == "error":
        sys.exit(f"ERROR: {resp.get('message')}")
    for msg in resp.get("messages", []):
        print(f"[{msg.get('ts', '')}] <{msg.get('nick', '')}> {msg.get('text', '')}")


def cmd_ask(args: argparse.Namespace) -> None:
    timeout = args.timeout
    resp = _send_request(
        {
            "type": "ask",
            "session_id": _get_session_id(),
            "channel": args.channel,
            "question": args.question,
            "timeout": timeout,
            "correlation_id": str(uuid.uuid4()),
        },
        timeout=timeout + 10,
    )
    if resp.get("type") == "error":
        sys.exit(f"ERROR: {resp.get('message')}")
    print(resp.get("answer", ""))


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentIRC skill: IRC send/read/ask")
    sub = parser.add_subparsers(dest="command", required=True)

    p_send = sub.add_parser("send", help="Post a message to a channel")
    p_send.add_argument("channel")
    p_send.add_argument("text")

    p_read = sub.add_parser("read", help="Fetch recent channel history")
    p_read.add_argument("channel")
    p_read.add_argument("--limit", type=int, default=20)

    p_ask = sub.add_parser("ask", help="Ask a question and block for answer")
    p_ask.add_argument("channel")
    p_ask.add_argument("question")
    p_ask.add_argument("--timeout", type=float, default=120.0)

    args = parser.parse_args()
    {"send": cmd_send, "read": cmd_read, "ask": cmd_ask}[args.command](args)


if __name__ == "__main__":
    main()
