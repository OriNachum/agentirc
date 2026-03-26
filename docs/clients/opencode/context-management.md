---
title: "Context Management"
parent: "Agent Client"
nav_order: 5
---

# Context Management

The agent has two tools for managing its context: `compact_context` and
`clear_context`. Both work through the ACP protocol -- the daemon sends the
command as a `session/prompt` to the OpenCode ACP session.

## compact_context

Summarizes the conversation and reduces context length.

```python
compact_context()
```

The skill signals the daemon, which sends `/compact` as a `session/prompt` to the
OpenCode ACP session. OpenCode handles the compaction itself -- it summarizes its
own conversation history into a condensed form and continues from there.

**When to use:**

- Transitioning from exploration to execution.
- Context is long after many tool calls and starting to feel unwieldy.
- After a supervisor whisper about drift (good time to refocus).
- Switching approach after failed attempts.

Compacting preserves IRC state (connection, channels, buffers) and the working
directory. The agent continues its current task with a lighter context.

## clear_context

Wipes the conversation and starts fresh.

```python
clear_context()
```

The skill signals the daemon, which sends `/clear` as a `session/prompt` to the
OpenCode ACP session. OpenCode starts a new conversation from scratch. IRC state
(connection, channels, buffers) and the working directory are unaffected.

**When to use:**

- Completely finished with one task and starting an unrelated one.
- Context is corrupted or too confused to compact usefully.
- Explicit instruction from a human to start fresh.

Unlike `compact_context`, clear does not retain a summary. The agent loses all
conversation history.

## How It Works Under the Hood

Unlike backends that use stdin commands, the OpenCode backend sends compact and
clear commands through the same ACP `session/prompt` mechanism used for regular
prompts. The daemon's IPC handler receives a `compact` or `clear` request from the
skill client and forwards it to the agent runner, which sends it as a prompt to the
active ACP session.

## Proactive Context Management

The agent's system prompt encourages proactive use of these tools rather than waiting
for context to become a problem:

> Use `compact_context()` when transitioning between phases of work. Use
> `clear_context()` when fully done with a task and the next task is unrelated.

The supervisor may also whisper a compaction suggestion if it detects context overload
or drift.
