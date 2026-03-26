---
title: "Context Management"
parent: "Agent Client"
nav_order: 5
---

# Context Management

The agent has two tools for managing its context: `compact_context` and
`clear_context`. Both work through the prompt queue -- compact/clear prompts are
sent to the Codex app-server thread as regular turns.

## compact_context

Summarizes the conversation and reduces context length.

```python
compact_context()
```

The skill signals the daemon, which enqueues a `/compact` prompt to the Codex
app-server thread. The prompt is processed as a regular `turn/start` request, asking
the agent to summarize its conversation history and continue from a condensed state.

**When to use:**

- Transitioning from exploration to execution.
- Context is long after many turns and starting to feel unwieldy.
- After a supervisor whisper about drift (good time to refocus).
- Switching approach after failed attempts.

Compacting preserves IRC state (connection, channels, buffers) and the working
directory. The Codex thread persists -- only the conversational context is condensed.

## clear_context

Wipes the conversation and starts fresh.

```python
clear_context()
```

The skill signals the daemon, which enqueues a `/clear` prompt to the Codex app-server
thread. The prompt is processed as a regular `turn/start` request, asking the agent to
reset its conversational state. IRC state (connection, channels, buffers) and the
working directory are unaffected.

**When to use:**

- Completely finished with one task and starting an unrelated one.
- Context is corrupted or too confused to compact usefully.
- Explicit instruction from a human to start fresh.

Unlike `compact_context`, clear does not retain a summary. The agent loses all
conversation history within the thread.

## Proactive Context Management

The agent's system prompt encourages proactive use of these tools rather than waiting
for context to become a problem:

> Use `compact_context()` when transitioning between phases of work. Use
> `clear_context()` when fully done with a task and the next task is unrelated.

The supervisor may also whisper a compaction suggestion if it detects context overload
or drift.
