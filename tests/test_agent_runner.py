import asyncio
import pytest
from clients.claude.agent_runner import AgentRunner


@pytest.mark.asyncio
async def test_spawn_process():
    runner = AgentRunner(
        command=["python3", "-u", "-c", "import time; time.sleep(60)"],
        directory="/tmp",
    )
    await runner.start()
    try:
        assert runner.is_running()
    finally:
        await runner.stop()
    assert not runner.is_running()


@pytest.mark.asyncio
async def test_stdin_pipe():
    runner = AgentRunner(
        command=["python3", "-u", "-c",
                 "import sys\nfor line in sys.stdin:\n    print('GOT:' + line.strip(), flush=True)"],
        directory="/tmp",
    )
    await runner.start()
    try:
        await runner.write_stdin("hello\n")
        line = await asyncio.wait_for(runner.read_stdout_line(), timeout=2.0)
        assert "GOT:hello" in line
    finally:
        await runner.stop()


@pytest.mark.asyncio
async def test_on_exit_callback():
    exit_codes = []
    async def on_exit(code):
        exit_codes.append(code)
    runner = AgentRunner(
        command=["python3", "-c", "pass"],
        directory="/tmp", on_exit=on_exit,
    )
    await runner.start()
    await asyncio.sleep(0.5)
    assert len(exit_codes) == 1
    assert exit_codes[0] == 0


@pytest.mark.asyncio
async def test_crash_detection():
    exit_codes = []
    async def on_exit(code):
        exit_codes.append(code)
    runner = AgentRunner(
        command=["python3", "-c", "raise SystemExit(1)"],
        directory="/tmp", on_exit=on_exit,
    )
    await runner.start()
    await asyncio.sleep(0.5)
    assert len(exit_codes) == 1
    assert exit_codes[0] == 1
