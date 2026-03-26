---
title: "Context Management"
parent: "Agent Client"
nav_order: 5
---

# Context Management

The agent has two tools for managing its context: `compact_context` and
`clear_context`. Both work through the Copilot agent's prompt queue -- the daemon
delivers them via `send_and_wait()` like any other prompt.

## compact_context

Requests context compaction in the Copilot session.

```python
compact_context()
```

The skill signals the daemon, which enqueues a `/compact` command to the agent
runner's prompt queue. The command is delivered to the Copilot session via
`send_and_wait()`.

**When to use:**

- Transitioning from exploration to execution.
- Context is long after many turns and starting to feel unwieldy.
- After a supervisor whisper about drift (good time to refocus).
- Switching approach after failed attempts.

Compacting preserves IRC state (connection, channels, buffers) and the working
directory. The agent continues its current task with a lighter context.

## clear_context

Requests a full context clear in the Copilot session.

```python
clear_context()
```

The skill signals the daemon, which enqueues a `/clear` command to the agent runner's
prompt queue. The command is delivered to the Copilot session via `send_and_wait()`.

**When to use:**

- Completely finished with one task and starting an unrelated one.
- Context is corrupted or too confused to compact usefully.
- Explicit instruction from a human to start fresh.

Unlike `compact_context`, clear does not retain a summary. The agent loses all
conversation history.

## How Context Management Differs from Claude

In the Claude backend, `/compact` and `/clear` are sent directly to Claude Code's
stdin. In the Copilot backend, these commands are delivered through the same prompt
queue as regular prompts, processed by `send_and_wait()`. The Copilot CLI handles
context management through its own internal mechanisms.

IRC state (connection, channel membership, and message buffers) is unaffected by
either operation -- it lives in the daemon, not in the Copilot session.

## Proactive Context Management

The agent's system prompt encourages proactive use of these tools rather than waiting
for context to become a problem:

> Use `compact_context()` when transitioning between phases of work. Use
> `clear_context()` when fully done with a task and the next task is unrelated.

The supervisor may also whisper a compaction suggestion if it detects context overload
or drift.
