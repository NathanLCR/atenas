"""Intent definitions and matching dataclass for the natural language interface."""

from __future__ import annotations

from dataclasses import dataclass, field

INTENT_TODAY = "today"
INTENT_WEEK = "week"
INTENT_DEADLINES = "deadlines"
INTENT_AVAILABILITY = "availability"
INTENT_PLAN = "plan"
INTENT_STUDY = "study"
INTENT_ADD_ASSIGNMENT = "add_assignment"
INTENT_SET_STATUS = "set_status"
INTENT_LIST_ASSIGNMENTS = "list_assignments"
INTENT_LIST_MODULES = "list_modules"
INTENT_LIST_SHIFTS = "list_shifts"
INTENT_ADD_NOTE = "add_note"
INTENT_NOTE_ACTION = "note_action"
INTENT_ASK_NOTES = "ask_notes"
INTENT_REMINDERS = "reminders"
INTENT_UNKNOWN = "unknown"

READ_INTENTS = {
    INTENT_TODAY,
    INTENT_WEEK,
    INTENT_DEADLINES,
    INTENT_AVAILABILITY,
    INTENT_PLAN,
    INTENT_STUDY,
    INTENT_LIST_ASSIGNMENTS,
    INTENT_LIST_MODULES,
    INTENT_LIST_SHIFTS,
    INTENT_NOTE_ACTION,
    INTENT_ASK_NOTES,
    INTENT_REMINDERS,
}

WRITE_INTENTS = {
    INTENT_ADD_ASSIGNMENT,
    INTENT_SET_STATUS,
    INTENT_ADD_NOTE,
}

CONFIDENCE_THRESHOLD = 0.7


@dataclass(frozen=True)
class IntentMatch:
    """Result of intent classification."""

    intent: str
    confidence: float
    slots: dict[str, str] = field(default_factory=dict)

    @property
    def is_read(self) -> bool:
        return self.intent in READ_INTENTS

    @property
    def is_write(self) -> bool:
        return self.intent in WRITE_INTENTS

    @property
    def is_confident(self) -> bool:
        return self.confidence >= CONFIDENCE_THRESHOLD
