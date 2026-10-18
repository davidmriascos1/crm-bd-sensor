import logging
import os
from datetime import datetime, time as dt_time, timezone

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatType
from telegram.error import BadRequest, Conflict, NetworkError
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import storage

load_dotenv()
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
OWNER_ID = int(os.environ["OWNER_ID"])
DIGEST_THRESHOLD_MINUTES = int(os.environ["DIGEST_THRESHOLD_MINUTES"])

DIGEST_HOUR_UTC = 13  # 24h clock, UTC

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
# httpx logs each request URL at INFO, which embeds the bot token.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def format_timedelta(delta):
    total_minutes = int(delta.total_seconds() // 60)
    days, rem_minutes = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(rem_minutes, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


async def record_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    sender = update.effective_user
    message = update.effective_message
    if chat is None or sender is None or message is None:
        return
    storage.record_activity(
        chat_id=chat.id,
        chat_title=chat.title or str(chat.id),
        sender_id=sender.id,
        is_owner=sender.id == OWNER_ID,
        message_at=message.date.astimezone(timezone.utc).isoformat(),
    )
    logger.info("Recorded activity for chat_id=%s sender_id=%s", chat.id, sender.id)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    sender = update.effective_user
    if sender is None or chat.type != ChatType.PRIVATE or sender.id != OWNER_ID:
        logger.warning(
            "Unauthorized /status attempt from chat_id=%s sender_id=%s",
            chat.id,
            sender.id if sender else None,
        )
        return

    rows = storage.get_status_rows()
    if not rows:
        await update.effective_message.reply_text("No groups recorded yet.")
        logger.info("Sent empty /status to chat_id=%s", update.effective_chat.id)
        return

    now = datetime.now(timezone.utc)
    lines = []
    for row in rows:
        last_at = datetime.fromisoformat(row["last_message_at"])
        who = "You" if row["is_owner"] else "They"
        lines.append(f"{row['chat_title']}: {who} spoke last, {format_timedelta(now - last_at)} ago")
    await update.effective_message.reply_text("\n".join(lines))
    logger.info("Sent /status to chat_id=%s with %d groups", update.effective_chat.id, len(rows))


async def digest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    sender = update.effective_user
    if sender is None or chat.type != ChatType.PRIVATE or sender.id != OWNER_ID:
        logger.warning(
            "Unauthorized /digest attempt from chat_id=%s sender_id=%s",
            chat.id,
            sender.id if sender else None,
        )
        return
    await send_daily_digest(context)


async def send_daily_digest(context: ContextTypes.DEFAULT_TYPE):
    rows = storage.get_overdue_rows(DIGEST_THRESHOLD_MINUTES)
    if not rows:
        text = "All clear: nothing waiting on you."
    else:
        now = datetime.now(timezone.utc)
        lines = ["Groups waiting on you:"]
        for row in rows:
            waiting_since = datetime.fromisoformat(row["waiting_since"])
            lines.append(f"- {row['chat_title']}: waiting {format_timedelta(now - waiting_since)}")
        text = "\n".join(lines)
    await context.bot.send_message(chat_id=OWNER_ID, text=text)
    logger.info("Sent daily digest: %d overdue groups", len(rows))


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = context.error
    if isinstance(err, Conflict):
        logger.critical("Conflict error: %s", err)
    elif isinstance(err, NetworkError) and not isinstance(err, BadRequest):
        logger.warning("Network error: %s", err)
    else:
        logger.error("Unhandled error: %s", err)


def main():
    storage.init_db()

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Group 0 records real conversation only (commands and service messages
    # excluded); group 1 handles /status separately either way.
    application.add_handler(
        MessageHandler(
            filters.ALL & filters.ChatType.GROUPS & ~filters.COMMAND & ~filters.StatusUpdate.ALL,
            record_group_message,
        ),
        group=0,
    )
    application.add_handler(CommandHandler("status", status_command), group=1)
    application.add_handler(CommandHandler("digest", digest_command), group=1)
    application.add_error_handler(error_handler)

    application.job_queue.run_daily(
        send_daily_digest, time=dt_time(hour=DIGEST_HOUR_UTC, minute=0), name="daily_digest"
    )

    application.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
