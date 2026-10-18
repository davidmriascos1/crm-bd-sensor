# crm-bd-sensor

Telegram bot that sits in BD (business development) groups and flags
when a client or partner may need a follow-up. Goal: fewer forgotten
follow-ups, no CRM to update by hand.

Status: personal learning experiment + future portfolio repo.
Not shared with any team. Tested only in a private test group.

## Who you're working with
- David: learning by building, not a senior developer.
- Explain each decision briefly: what, how, why, and the trade-off.
- Spell out acronyms on first use. A short metaphor first helps.
- Record every decision in docs/DECISIONS.md (concise table:
  decision / chosen / rejected / why).
- Small steps. One MVP stage at a time. Ask before installing packages.

## Hard rules
- Bot API only (python-telegram-bot). No userbot / Telethon.
- Metadata only: chat id, chat title, sender id, is-owner flag,
  timestamp. NEVER store message text.
- No LLM call per message.
- SQLite + one Python process. No Docker, no dashboards, no cloud.
- Secrets live in .env (gitignored). Never print or log the token.
  Set the httpx logger to WARNING: its INFO lines log the full
  request URL, which embeds the bot token.
- Never read or print .env; only append new keys, and tell David
  which key to add if a value is needed.
- Never read or touch ~/pendientes-bot (another live bot on this box).
- Kill processes by full path or PID, never by bare filename —
  pendientes-bot also runs a bot.py.
- Never git push. Commit when asked; David reviews and pushes.

## Environment
- Server davidagent, Ubuntu 26.04, ~3.4 GiB RAM shared with
  pendientes-bot. Keep memory use small.
- Python venv at .venv. Run `python -m py_compile` before commits.
- Later: systemd user service + journald, like pendientes-bot.

## Patterns to reuse from pendientes-bot
- `logging` module, not print; log AFTER the await it reports.
- Error handler: Conflict -> CRITICAL; NetworkError (but not
  BadRequest, which subclasses it) -> WARNING; else ERROR.
- asyncio.sleep, never time.sleep.
- drop_pending_updates=False.
- DB path absolute (relative to the script), never bare relative.

## MVP 0 scope
- Bot privacy mode disabled in BotFather (else it sees no messages).
- Record last activity per group: who spoke last, when.
- OWNER_ID in .env identifies David's own messages.
- /status: list groups, who spoke last, how long ago.
- Daily digest: groups where the other side spoke last and David
  hasn't replied in > N hours.
