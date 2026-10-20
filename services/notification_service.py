"""Notification service – persistent in-app notifications stored in MySQL.

Every service that changes an order or donation calls notify() so that the
recipient user sees a message the next time they log in.
"""
from __future__ import annotations

from database.database import query_all, execute


def notify(user_id: int, message: str) -> None:
    """Insert a new notification for *user_id*.  Best-effort: swallows DB errors."""
    try:
        execute(
            "INSERT INTO notifications (user_id, message) VALUES (%s, %s)",
            (user_id, message),
        )
    except Exception:
        pass  # Notifications must not break the calling transaction


def get_notifications(user_id: int, unread_only: bool = False) -> list[dict]:
    """Return notifications for *user_id*, newest first."""
    sql = "SELECT * FROM notifications WHERE user_id = %s"
    params: tuple = (user_id,)
    if unread_only:
        sql += " AND is_read = 0"
    sql += " ORDER BY created_at DESC"
    return query_all(sql, params)


def mark_read(notification_id: int) -> None:
    execute("UPDATE notifications SET is_read = 1 WHERE id = %s", (notification_id,))


def mark_all_read(user_id: int) -> None:
    execute("UPDATE notifications SET is_read = 1 WHERE user_id = %s", (user_id,))


def unread_count(user_id: int) -> int:
    from database.database import query_one
    row = query_one(
        "SELECT COUNT(*) AS cnt FROM notifications WHERE user_id = %s AND is_read = 0",
        (user_id,),
    )
    return int(row["cnt"]) if row else 0
