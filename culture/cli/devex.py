"""`culture devex` — passthrough to the standalone agex CLI.

Also registers universal-verb handlers for the ``devex`` topic so
``culture explain devex`` / ``culture overview devex`` /
``culture learn devex`` route through culture's universal-verb path.

Under the hood, ``devex`` is powered by the standalone ``agex-cli``
(``agent_experience`` package). The command name differs for
familiarity with the developer-experience vocabulary; the underlying
tool is the same.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import sys

from culture.cli import introspect

NAME = "devex"


def _run_devex(argv: list[str]) -> None:
    """Invoke the underlying agex typer app in-process.

    Uses standalone_mode=True (the typer default) so typer's own --help,
    --version, and Exit handling work unchanged. Typer calls ``sys.exit``
    when done, raising ``SystemExit``; this function lets that propagate
    so the caller (the ``culture devex`` passthrough) exits with the code
    the user expects. Callers that need to capture output and translate
    the exit into a return value should use :func:`_capture_devex` instead.
    """
    try:
        from agent_experience.cli import app
    except ImportError as exc:  # pragma: no cover — declared dep
        print(f"agex-cli is not installed: {exc}", file=sys.stderr)
        sys.exit(2)
    app(args=argv)


def _capture_devex(argv: list[str]) -> tuple[str, int]:
    """Run devex with stdout + stderr captured, translating SystemExit.

    The universal-verb handlers need ``(output, exit_code)`` rather than a
    process-level exit, so we deliberately catch ``SystemExit`` here and
    translate it into a return value. The :func:`_run_devex` variant is for
    the passthrough path where the exit must propagate.
    """
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            _run_devex(argv)
    except SystemExit as exc:  # NOSONAR S5754 — see docstring
        # typer calls sys.exit() on completion even for success, so this
        # is the normal exit path; the trailing `return ... 0` only runs
        # if _run_devex somehow returns without raising (defensive).
        code = exc.code
        if code is None:
            return buf.getvalue(), 0
        if isinstance(code, int):
            return buf.getvalue(), code
        return buf.getvalue() + str(code), 1
    return buf.getvalue(), 0


# --- universal-verb topic handlers for ``devex`` ---------------------------


def _devex_explain(_topic: str | None) -> tuple[str, int]:
    # The underlying agex library refers to itself as "agex"; that's what
    # we pass to its own explain verb. The culture-facing name is devex.
    return _capture_devex(["explain", "agex"])


def _devex_overview(_topic: str | None) -> tuple[str, int]:
    return _capture_devex(["overview", "--agent", "claude-code"])


def _devex_learn(_topic: str | None) -> tuple[str, int]:
    return _capture_devex(["learn", "--agent", "claude-code"])


introspect.register_topic(
    "devex",
    explain=_devex_explain,
    overview=_devex_overview,
    learn=_devex_learn,
)


# --- CLI group protocol ---------------------------------------------------


def register(subparsers: "argparse._SubParsersAction") -> None:
    # prefix_chars=chr(0) means the devex subparser has no recognized flag
    # prefix character, so every token (including --help, --version) is
    # treated as positional and captured in devex_args for typer to handle.
    p = subparsers.add_parser(
        NAME,
        help="Run the agex developer-experience CLI via passthrough",
        add_help=False,
        prefix_chars=chr(0),
    )
    p.add_argument("devex_args", nargs=argparse.REMAINDER, help="Arguments passed to agex")


def dispatch(args: argparse.Namespace) -> None:
    rest = list(getattr(args, "devex_args", []) or [])
    _run_devex(rest)
