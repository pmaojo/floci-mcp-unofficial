---
name: floci-triage
description: Diagnose failed messages in the local emulator. Finds dead-letter queues, inspects what is stuck and why, then redrives only after the user confirms. Use when messages are not arriving, a consumer keeps failing, or the user mentions a DLQ.
argument-hint: "[queue URL or name]"
---

# Floci message triage

Find stuck messages, explain them, and only then move them.

**Toolsets needed:** `ops` (for the DLQ tools) and `messaging`. `ops` is not enabled by default: if `list_dead_letter_queues` is missing, call `enable_toolset` with `ops` if that tool exists; otherwise tell the user to set `FLOCI_TOOLSETS=core,storage,messaging,ops` and restart.

## Steps

1. Call `list_dead_letter_queues`. If none has messages, say the queues are healthy and stop.
2. For each DLQ with messages (or the one in `$ARGUMENTS`), call `inspect_dlq_messages`. This does not consume them.
3. Call `get_sqs_queue_attributes` on the source queue to show the redrive policy and visibility timeout.
4. Explain the likely cause from the bodies, receive counts and attributes. Quote one or two real messages, trimmed.
5. **Ask the user before redriving.** `redrive_dlq` writes to the source queue. Only call it after an explicit yes, and say how many messages it moved.

## Rules

- Never call `purge_sqs_queue` or `delete_sqs_queue` as part of triage.
- If the fix is in code, say that redriving before the fix will send the same messages back to the DLQ.
