# DIKW Memory System for Hermes Agent (Holographic Edition)

A pure SQLite memory system for [Hermes Agent](https://hermes-agent.nousresearch.com), built on the built-in Holographic plugin.

Zero external services, zero Docker, zero network dependency.

## What's inside

| File | Purpose |
|------|---------|
| `SOUL.md` | Agent personality — rules, thinking protocol, memory tool guide |
| `AGENTS.md` | Workspace directory standards |
| `docs/记忆系统使用指南.md` | Complete DIKW memory system SOP |

### Source code

| File | Purpose |
|------|---------|
| `agent/skill_auto_trigger.py` | Auto-trigger skills by keyword match (140 lines) |
| `agent/fact_feedback_loop.py` | Automatic trust score calibration (344 lines) |
| `agent/tool_executor_vault_duty.patch` | Vault-write enforcement patch for tool_executor.py |

### Skills

| File | Purpose |
|------|---------|
| `skills/dikw-memory-flow.md` | DIKW information triage flow |
| `skills/memory-capacity-management.md` | Auto-DIKW分流 when MEMORY.md exceeds 85% |
| `skills/fact-feedback-loop.md` | Trust score calibration service |

## Four-layer self-healing closed loop

```
① skill auto-trigger     → keyword match injects skill content on the fly
② capacity management     → auto DIKW分流 when MEMORY.md > 85%
③ trust calibration       → weekly statistics-based trust score tuning
④ vault-write enforcement → auto [DUTY] reminder when writing docs to vault
```

## License

MIT
