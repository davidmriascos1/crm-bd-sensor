# crm-bd-sensor

A Telegram bot that sits in your BD (business development) group chats
and tells you which ones are waiting on a reply from you — without a
CRM to update by hand and without storing what anyone wrote.

## Why

Follow-ups fall through the cracks when they live scattered across
group chats. The alternative is usually "update the CRM after every
conversation," which nobody does consistently. This bot watches
passively and surfaces one thing: *who spoke last, and for how long
have you been silent.*

## Status

MVP 0 — personal learning project, tested only in a private test
group. Not hardened for multiple owners or large group counts.

## Privacy design

- **Metadata only.** The bot stores chat id, chat title, sender id,
  an is-owner flag, and timestamps — never message text, and no LLM
  call ever sees your messages.
- **Bot API, not a userbot.** Runs as a real Telegram bot
  (`python-telegram-bot`), not a logged-in user account — avoids the
  ToS risk of automating a personal account.
- **Owner-only commands.** `/status` and `/digest` only answer in a
  private chat with the configured owner; anyone else gets silently
  ignored (and logged, with no message content).
- **One local SQLite file.** No external services, no dashboards, no
  cloud — everything stays on the machine you run it on.

## How it works

- Bot privacy mode must be **disabled** in BotFather, or it won't see
  group messages at all.
- Every real conversational message in a tracked group updates a
  single row per chat: who spoke last, and when.
- If the other side speaks and the owner hasn't replied yet, a
  `waiting_since` timestamp starts — cleared the moment the owner
  replies.
- `/status` (DM only, owner only) lists every tracked group and who
  spoke last, how long ago. Example reply:
  ```
  Acme Corp BD: They spoke last, 3h 12m ago
  Beta Partners: You spoke last, 1d 4h ago
  ```
- `/digest` (DM only, owner only) sends the same summary as the daily
  scheduled digest, useful for testing on demand.
- A daily scheduled digest lists any group still waiting past
  `DIGEST_THRESHOLD_MINUTES`, or sends "All clear: nothing waiting on
  you." if none are — doubling as a heartbeat that the bot is alive.
  It runs at 13:00 UTC (08:00 Bogotá) by default, set via
  `DIGEST_HOUR_UTC` in `bot.py`.

## Running it

1. Create a bot with [@BotFather](https://t.me/BotFather) and get a
   token. **Disable privacy mode** for the bot (BotFather →
   `/mybots` → your bot → Bot Settings → Group Privacy → Turn off).
2. Clone the repo and set up the virtualenv:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
   Tested on Python 3.14 with `python-telegram-bot` 22.x.
3. Create a `.env` file (never committed) with:
   ```
   TELEGRAM_TOKEN=your-bot-token
   OWNER_ID=your-telegram-user-id
   DIGEST_THRESHOLD_MINUTES=1440
   ```
   `OWNER_ID` is your numeric Telegram user id (not your username) —
   you can get it from a bot like @userinfobot.
4. Add the bot to the group chats you want it to watch.
5. Run it:
   ```
   python3 bot.py
   ```
6. DM the bot `/status` or `/digest` from the `OWNER_ID` account to
   confirm it's working.

## Limitations

- **Single owner only.** `OWNER_ID` is one person — if a teammate
  replies in the group, the wait is not cleared, since the bot has
  no concept of "someone on your side answered."
- **No history before the bot joined.** It only sees messages sent
  after it was added to a group; past activity isn't backfilled.
- **Chat titles are stored as-is**, and a BD group's title often
  names the client or partner — anyone with DB access sees that,
  even though no message content is stored.

## What it is not

No message text storage, no LLM, no Docker, no multi-user support,
no web dashboard. It's a single SQLite file and one Python process,
deliberately kept small.

## What I learned

Built step by step, with every decision recorded in
[docs/DECISIONS.md](docs/DECISIONS.md). A few things that only showed
up once this was running against real Telegram traffic:

- `httpx`'s default logging writes the full request URL at `INFO`,
  which embeds the bot token — easy to leak into a log file without
  ever calling `logging` yourself.
- `python-telegram-bot` 21.x breaks under Python 3.14, since
  `asyncio.get_event_loop()` no longer auto-creates a loop on the
  main thread; needed 22.x.
- Removing/re-adding the bot to a group, or running a command,
  generates Telegram updates that look like normal messages unless
  explicitly filtered out — otherwise they get recorded as real
  conversational activity.
- Telegram can redeliver updates after a restart, so writes have to
  be idempotent based on the message's own timestamp, not wall-clock
  time when the write happens.
