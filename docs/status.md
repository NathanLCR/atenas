# Skill Spec — Status

## Purpose
System health and context overview. Confirms the agent is running, lists active skills, shows student context summary. No LLM dependency — fully deterministic. Must work even when all LLMs are unavailable.

## Commands

| Command | Description |
|---|---|
| `/ping` | Returns `pong` |
| `/status` | System status + student context summary |
| `/skills` | Lists registered skills and availability |

## Inputs
- `/ping` — none.
- `/status` — reads SQLite counts only: active assignments, deadlines in the next 7 days, work shifts in the current calendar week. Student name is a hardcoded constant ("Nathan") in Phase 1. LLM status lines are static placeholders (no live Ollama ping or cloud check yet — see Phase 3).
- `/skills` — reads skill registry.

## Outputs

### `/ping`
```
🏓 pong
```

### `/status`
```
🟢 Atenas — Online

Student: Nathan
📚 Active assignments: 3
⏰ Deadlines this week: 1
🏢 Work shifts this week: 4
💡 Local LLM: ⬜ Mock only
☁️  Cloud LLM: ⬜ Disabled
```

`Deadlines this week` counts assignments due within the next 7 days (rolling
window from today). `Work shifts this week` counts the current Mon–Sun calendar
week. The two windows differ by design. Live LLM availability replaces the
static placeholder lines in Phase 3.

### `/skills`
```
📦 Registered Skills
✅ status        — System health and context
```

Only registered skills are listed. In Phase 1 that is `status` alone; later
phases add rows as their skills register. The ✅/⬜ icon reflects the skill's
`enabled` flag, not implementation status.

## Storage Impact
Read-only. No writes.

## LLM Usage
None.

## Safety Rules
- No destructive actions.
- Must not expose file paths, tokens, or secrets.

## Test Cases
| Test | Expected |
|---|---|
| `/ping` | Returns `pong` within 1s |
| `/status` with empty DB | Online status with zeros |
| `/status` with data | Correct counts |
| `/status` with unreadable DB | Falls back to zero counts, still Online |
| `/skills` with 1 skill registered | Lists it correctly |
