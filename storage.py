import os
import sqlite3
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crm_bd_sensor.db")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS group_activity (
                chat_id         INTEGER PRIMARY KEY,
                chat_title      TEXT NOT NULL,
                last_sender_id  INTEGER NOT NULL,
                is_owner        INTEGER NOT NULL,
                last_message_at TEXT NOT NULL,
                waiting_since   TEXT
            )
            """
        )


def record_activity(chat_id, chat_title, sender_id, is_owner, message_at):
    # waiting_since starts the clock on the FIRST unanswered message from the
    # other side; the WHERE guard skips the whole update if this message is
    # older than what's stored, since restarts can replay old updates.
    waiting_since = None if is_owner else message_at
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO group_activity
                (chat_id, chat_title, last_sender_id, is_owner, last_message_at, waiting_since)
            VALUES
                (:chat_id, :chat_title, :sender_id, :is_owner, :message_at, :waiting_since)
            ON CONFLICT (chat_id) DO UPDATE SET
                chat_title      = excluded.chat_title,
                last_sender_id  = excluded.last_sender_id,
                is_owner        = excluded.is_owner,
                last_message_at = excluded.last_message_at,
                waiting_since   = CASE
                    WHEN excluded.is_owner = 1 THEN NULL
                    WHEN group_activity.waiting_since IS NOT NULL THEN group_activity.waiting_since
                    ELSE excluded.waiting_since
                END
            WHERE excluded.last_message_at > group_activity.last_message_at
            """,
            {
                "chat_id": chat_id,
                "chat_title": chat_title,
                "sender_id": sender_id,
                "is_owner": int(is_owner),
                "message_at": message_at,
                "waiting_since": waiting_since,
            },
        )


def get_status_rows():
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM group_activity ORDER BY chat_title COLLATE NOCASE"
        ).fetchall()
    return [dict(row) for row in rows]


def get_overdue_rows(threshold_minutes):
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=threshold_minutes)).isoformat()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM group_activity
            WHERE waiting_since IS NOT NULL AND waiting_since <= :cutoff
            ORDER BY waiting_since ASC
            """,
            {"cutoff": cutoff},
        ).fetchall()
    return [dict(row) for row in rows]
