# Post-MVP Phase 11 — Multi-User Readiness

## Status

Post-MVP optional.

## Goal

Prepare Atenas for use by other working students.

## In scope

- user/profile model
- user-specific modules/classes/shifts/assignments
- onboarding flow
- per-user Telegram allowlist/config
- migration plan from single-user data

## Out of scope

- public SaaS launch
- payments
- full enterprise auth
- complex RBAC

## Key design challenge

The current system is optimized for one real user.

Multi-user support should not degrade personal usability.

## Exit criteria

Phase 11 is complete when the codebase can support more than one user without data mixing.
