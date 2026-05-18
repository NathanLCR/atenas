# Skill Spec — Study Planner

## Purpose
Generate realistic daily/weekly study plans that respect work shifts, class
sessions, deadlines, fatigue, and available time.

**Division of labour (the core design rule):** *code owns all structure and
all times; the LLM only chooses what to do inside slots code already fixed.*
Availability, slot boundaries, and intensity caps are computed
deterministically. The LLM never authors or edits a time. This is what makes
the safety guarantee ("a plan never ignores a known shift") enforceable
rather than aspirational — a hallucinated time cannot exist in the output
because the output schema has no LLM-writable time field.

## Commands

| Command | Description |
|---|---|
| `/study today` | Generate today's plan |
| `/study week` | Generate the week's plan |
| `/plan today` | Alias |
| `/plan week` | Alias |

## What the LLM is actually for
Not scheduling — code schedules. The LLM does the judgement code is bad at:
choosing *which* prioritised task best fits a given slot, titling the block,
sequencing related work sensibly, and writing the human-readable `reason`.
It receives code-authored `AvailabilitySlot`s + a code-prioritised task list
and returns `BlockAssignment`s keyed by `slot_id`. Code then validates every
assignment and materialises the final plan. If the LLM is unavailable, a
deterministic fallback (fill slots by priority order) still produces a valid,
if less nuanced, plan — satisfying NFR-01.

## Planning Pipeline (deterministic stages 1–4 & 6; LLM only stage 5)

1. **Load hard blocks.** Work shifts (`work_shifts`) and class sessions
   (`class_sessions`) for the target date(s), expanding class recurrence.
2. **Compute availability.** See *Availability Algorithm* below.
3. **Apply fatigue caps in code.** Each availability slot gets a
   `max_intensity` from the *Fatigue Rules*. Slots are split at cap
   boundaries so a slot has a single cap.
4. **Prioritise tasks in code.** Sort candidate tasks by
   `deadline_risk` (desc), then `priority` (desc), then shortest
   `estimated_minutes` (to bank quick wins). Deterministic tie-break: by
   `task.id`.
5. **LLM assigns tasks to slots.** Input: the `AvailabilitySlot[]` and the
   ranked task list. Output: `DailyPlanGenerated` (`BlockAssignment[]` keyed
   by `slot_id`, `intensity ≤ slot.max_intensity`, `reason`). No times.
6. **Validate & persist in code.** Reject any assignment whose `slot_id` is
   unknown or whose `intensity` exceeds the slot cap; clamp on reject by
   re-deriving deterministically. Materialise final blocks by joining
   assignments → slots (times come from the slot). Save to
   `memory/plans/daily/` and `memory/plans/weekly/` + `study_blocks`.

## Availability Algorithm (deterministic, fully specified)

Inputs: target date `D`, `settings.timezone`, hard blocks for `D`,
`memory/preferences.yaml`.

```
waking_start  = preferences.day_start            (default 08:00)
waking_end    = preferences.day_end              (default 23:00)
min_slot      = preferences.min_study_minutes    (default 30)
meal_blocks   = preferences.meals                (default 13:00–13:30, 19:00–19:45)
buffer        = preferences.transition_minutes   (default 15)

1. window = [waking_start, waking_end] on D, in settings.timezone.
2. hard = work shifts ∪ class sessions on D, each expanded to
   [start, end]. For a work shift, also subtract commute_minutes BEFORE
   start and AFTER end (travel is not study time).
3. busy = hard ∪ meal_blocks.
4. free = window minus busy (interval subtraction).
5. For each free interval, shrink by `buffer` on any edge that abuts a
   hard block (no context-switch study against a wall).
6. Drop intervals shorter than `min_slot`.
7. Emit each remaining interval as an AvailabilitySlot (slot_id = index).
```

All arithmetic is timezone-aware in `settings.timezone`; DST transitions use
the zone's real offset for `D`. Stored timestamps remain UTC ISO 8601.

## Fatigue Rules (applied in code → `max_intensity` per slot)

| Condition | `max_intensity` for affected slots |
|---|---|
| Previous day's shift ended ≥ 23:00 AND slot starts before 10:00 | `recovery` |
| Same-day `fatigue_level == high` | `light` |
| Same-day `fatigue_level == medium` | `medium` |
| Class immediately after a commute ≥ 45 min, slot directly before it | `light` |
| Otherwise | `deep` |

Heavy-week reduction: if the target week has ≥ 4 shifts, after slot
computation drop lowest-priority assignments until total planned study
minutes for the week are ≤ 70% of the equivalent light-week total
(i.e. a ≥ 30% reduction). This is enforced in code, not requested of the LLM.

## Deadline Risk Score (deterministic, used in stage 4)

For an assignment/task with a deadline:

```
hours_left      = max(0, hours_between(now_tz, deadline))
hours_needed    = estimated_minutes / 60
slack_ratio     = hours_left / max(hours_needed, 0.5)
priority_weight = {low:1.0, medium:1.25, high:1.5, critical:2.0}[priority]

deadline_risk   = clamp( priority_weight / max(slack_ratio, 0.1), 0.0, 10.0 )
```

Higher = more urgent. No deadline → `deadline_risk = priority_weight * 0.1`
(stays on the radar, never urgent). The formula is pure and unit-tested
independently of the LLM.

## LLM Usage
- Daily: local LLM default. Schema: `DailyPlanGenerated`.
- Weekly: cloud LLM default (more conflicting constraints) when the cloud
  fallback is enabled; otherwise the deterministic fallback runs locally.
- Escalation/terminal-failure behaviour: see AGENT_POLICY "LLM Routing".

## Acceptance
The plan must pass every invariant in ROADMAP "PLAN QUALITY" on the seeded
fixture week, automatically. That suite is the definition of done for this
skill — "realistic" is not asserted, it is tested.

## Phase
Phase 8. Built only after Work Schedule (5), Class Timetable (6) and
Assignments (7), because it consumes all three. Not implemented in Phase 1.
