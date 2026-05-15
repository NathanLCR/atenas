# Skill Spec — Study Planner

## Purpose
Generate realistic daily/weekly study plans that respect work shifts, class sessions, deadlines, fatigue, and available time. LLM-assisted but deterministic-first: availability and fatigue are computed in code, LLM only assigns tasks to blocks.

## Commands

| Command | Description |
|---|---|
| `/study today` | Generate today's plan |
| `/study week` | Generate the week's plan |
| `/plan today` | Alias |
| `/plan week` | Alias |

## Planning Pipeline (deterministic)
1. Load work shifts and class sessions
2. Compute availability blocks (subtract hard blocks from waking hours)
3. Apply fatigue intensity caps in code
4. Prioritise tasks by deadline proximity and priority
5. LLM assigns tasks to pre-computed blocks (DailyPlanGenerated schema)
6. Validate and save

## Fatigue Rules (applied in code, not LLM)
| Condition | Intensity cap |
|---|---|
| Previous shift ended after 23:00 AND block before 10:00 | `recovery` only |
| Same day fatigue == `high` | `light` max |
| Heavy week (≥ 4 shifts) | Reduce total hours 30% |

## LLM Usage
- Daily: local LLM default. Schema: `DailyPlanGenerated` (capacity + reason + warnings).
- Weekly: cloud LLM default (complexity).

## Phase
Phase 6. Not implemented in Phase 1.
