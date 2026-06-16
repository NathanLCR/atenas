# Getting Started

This guide takes a new machine from a fresh clone to a working Atenas study
assistant answering in Telegram. Atenas runs locally and is single-user by
default; nothing here exposes a public service.

Estimated time: 15–20 minutes, most of it downloading local models.

## 1. Prerequisites

- **Python 3.11** (`python3.11 --version`).
- **Ollama** for the local LLM — https://ollama.com/download.
- A **Telegram account** to create a bot and talk to it.

## 2. Clone and install

```bash
git clone https://github.com/nathanlcr/atenas.git
cd atenas
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .        # installs the `atenas` CLI
```

The first run creates the gitignored runtime directories (`data/`, `logs/`,
`memory/`, `inbox/`, `output/`) automatically — you do not need to make them.

## 3. Install the local models (Ollama)

Atenas defaults to Ollama as the local LLM provider. Pull the default models
referenced in `.env.example`:

```bash
ollama pull llama3.1:8b        # OLLAMA_MODEL — main reasoning/agent model
ollama pull llama3.2           # OLLAMA_SMALL_MODEL — lightweight tasks
ollama pull nomic-embed-text   # OLLAMA_EMBEDDING_MODEL — retrieval embeddings
```

Make sure the Ollama server is running (`ollama serve`, or the desktop app).
By default Atenas talks to it at `http://localhost:11434`.

> External cloud LLM providers (OpenAI, OpenRouter) are **opt-in data egress**
> and disabled by default. Leave `ENABLE_CLOUD_FALLBACK=false` to keep all
> prompt and tool-result data on your machine.

## 4. Create your Telegram bot

Telegram is the primary interface. You need a bot token and your own numeric
user ID for the allowlist.

1. **Get a bot token.** In Telegram, message [@BotFather](https://t.me/BotFather),
   send `/newbot`, follow the prompts, and copy the token it gives you
   (looks like `123456789:ABC-DEF...`).
2. **Find your numeric user ID.** Message [@userinfobot](https://t.me/userinfobot)
   (or any "what is my Telegram id" bot) and copy the numeric `id`.

The allowlist is enforced before any command, LLM call, retrieval, or tool
runs. If the allowlist is empty while a token is set, Telegram access is
effectively closed — add at least your own ID.

## 5. Configure your environment

Copy the example file and fill in the two Telegram values:

```bash
cp .env.example .env
```

Edit `.env` and set at least:

```bash
TELEGRAM_BOT_TOKEN=123456789:ABC-DEF...   # from BotFather
TELEGRAM_ALLOWED_USER_IDS=123456789        # your numeric id (comma-separated for more)
NOTIFICATIONS_CHAT_ID=123456789            # usually your own id, for reminders
TIMEZONE=Europe/Dublin                     # your IANA timezone
```

The remaining defaults (Ollama URLs/models, cloud disabled, local-only guard)
are sensible for a first run. Never commit `.env` — it is gitignored.

## 6. Verify the setup

Run the built-in diagnostic. It creates runtime directories, initializes the
database, and checks Ollama, models, the Telegram allowlist, and the
local-only guard:

```bash
atenas doctor
```

Resolve anything it flags (missing model, empty allowlist, unreachable Ollama)
before starting the app.

## 7. Run Atenas

```bash
.venv/bin/uvicorn app.main:app --reload
```

On startup Atenas launches the Telegram bot (when a token is set) alongside the
local API and dashboard. Open Telegram, send `/start` to your bot, and try:

- `/status` — a deterministic slash command.
- A plain message like *"what's due this week?"* — routed to the LLM tool agent.

The local dashboard and API are support surfaces bound to `127.0.0.1:8000`:

- Dashboard: http://127.0.0.1:8000/dashboard/
- Health: http://127.0.0.1:8000/health

Do not expose these on a LAN or public host. See `docs/SECURITY.md`.

## 8. Run the tests (optional)

```bash
.venv/bin/pytest -q
```

The suite mocks LLM providers and uses isolated databases, so it passes
without a running Ollama or Telegram token.

## Troubleshooting

- **`atenas: command not found`** — run `.venv/bin/pip install -e .`, or invoke
  via `.venv/bin/atenas doctor`.
- **Ollama unreachable** — start `ollama serve` and confirm
  `OLLAMA_BASE_URL`. A non-loopback URL is refused unless
  `allow_external_ollama=true`.
- **Model MISSING in doctor** — `ollama pull <model>` for the name it reports.
- **Bot ignores you** — confirm your numeric ID is in
  `TELEGRAM_ALLOWED_USER_IDS`; the allowlist is checked before anything else.
- **Invalid timezone** — `TIMEZONE` must be a valid IANA name, e.g.
  `America/Sao_Paulo`.

## Next steps

- `docs/AGENT_LOOP.md` — how the agent loop and action-tier governance work.
- `docs/PRODUCT_SPEC.md` — what Atenas is and who it is for.
- `docs/SECURITY.md` — the local-only and Telegram security contract.
