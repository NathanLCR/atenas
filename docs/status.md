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
- `/status` — reads SQLite (assignment/deadline/shift counts), `memory/profile.md`, Ollama ping, cloud status.
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
💡 Local LLM: ✅ Available
☁️  Cloud LLM: ✅ Available
```

### `/skills`
```
📦 Registered Skills
✅ status        — System health and context
⬜ memory        — Not yet implemented
⬜ work_schedule — Not yet implemented
```

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
| `/status` with Ollama offline | Shows `❌ Unavailable` |
| `/skills` with 1 skill registered | Lists it correctly |
