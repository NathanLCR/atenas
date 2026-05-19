"""Prompt templates for natural language intent classification."""

from __future__ import annotations

INTENT_LIST = [
    "today",
    "week",
    "deadlines",
    "availability",
    "plan",
    "study",
    "add_assignment",
    "set_status",
    "list_assignments",
    "list_modules",
    "list_shifts",
    "add_note",
    "note_action",
    "ask_notes",
    "reminders",
]

CLASSIFICATION_PROMPT = """You are an intent classifier for a study assistant called Atenas.
Classify the user's message into exactly one of these intents:

{intent_list}

Intent descriptions:
- today: user asks about today's schedule, plan, or what's happening today
- week: user asks about the weekly schedule or this week's overview
- deadlines: user asks about upcoming deadlines or due dates
- availability: user asks about free time, study hours, or available windows
- plan: user asks for a study plan or weekly plan
- study: user asks what to study now or what's next to study
- add_assignment: user wants to add a new assignment, task, or deadline
- set_status: user wants to update assignment status (done, in_progress, submitted, etc.)
- list_assignments: user wants to see their assignments
- list_modules: user wants to see their study modules
- list_shifts: user wants to see their work shifts
- add_note: user wants to add a new note
- note_action: user wants to summarize, explain, or get questions/flashcards from a specific note (e.g. "summarise note 5", "explain note 3")
- ask_notes: user asks a question about their notes or wants to search notes by topic
- reminders: user asks about their reminders or notifications

Extract relevant slots from the message. Common slots:
- title: assignment or note title
- due_at: due date/time (keep as natural language if not a clear date)
- priority: priority level (low/normal/high or 1-5)
- module: module name or code
- estimated_hours: estimated study hours
- note_id: note number or ID
- action: action for a note (summarize, explain, questions, flashcards)
- query: search query for notes
- status: assignment status (todo, in_progress, submitted, done, cancelled)
- content: note body content

Return ONLY valid JSON, nothing else:
{{"intent": "<intent_name>", "confidence": <0.0-1.0>, "slots": {{...}}}}

Examples:
User: "what's my plan for today?"
{{"intent": "today", "confidence": 0.95, "slots": {{}}}}

User: "add an assignment: ML exam due Friday at 5pm, priority high"
{{"intent": "add_assignment", "confidence": 0.92, "slots": {{"title": "ML exam", "due_at": "Friday at 5pm", "priority": "high"}}}}

User: "what do my notes say about CNNs?"
{{"intent": "ask_notes", "confidence": 0.93, "slots": {{"query": "CNNs"}}}}

User: "summarise note 5"
{{"intent": "note_action", "confidence": 0.90, "slots": {{"note_id": "5", "action": "summarize"}}}}

User: "how many study hours do I have?"
{{"intent": "availability", "confidence": 0.88, "slots": {{}}}}

User: "hello"
{{"intent": "ask_notes", "confidence": 0.3, "slots": {{"query": "hello"}}}}

Now classify this message:
User: {user_message}
"""
