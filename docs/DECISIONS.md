# Architecture Decisions

## 2026-05-21 — Planning Contract

Atenas keeps the v1 requirement that work fatigue affects planning intensity.
The planner remains deterministic: code computes study windows and their
maximum intensity, then assigns work without LLM-authored times.

## 2026-05-21 — NL Architecture

The canonical natural-language path is `AgentLoop` plus `ToolRegistry`.
`NLRouter` and `NLClassifier` are legacy compatibility surfaces only. New safety,
tooling, and product behavior must land in `ToolRegistry`, not in `NLRouter`.
