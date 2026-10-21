import json
from typing import Any


def record(
    conn: Any,
    *,
    actor_user_id: str | None,
    entity_type: str,
    entity_id: str,
    action: str,
    detail: dict | None = None,
) -> dict:
    return conn.execute(
        """
        INSERT INTO events (at, actor_user_id, entity_type, entity_id, action, detail)
        VALUES (clock_timestamp(), %s::uuid, %s, %s::uuid, %s, %s::jsonb)
        RETURNING *
        """,
        (actor_user_id, entity_type, entity_id, action, json.dumps(detail or {})),
    ).fetchone()


def for_entity(conn: Any, entity_type: str, entity_id: str) -> list[dict]:
    return conn.execute(
        """
        SELECT * FROM events
        WHERE entity_type = %s AND entity_id = %s::uuid
        ORDER BY at DESC, id
        """,
        (entity_type, entity_id),
    ).fetchall()


def for_change(conn: Any, change_id: str) -> list[dict]:
    return conn.execute(
        """
        SELECT * FROM events
        WHERE (entity_type = 'change' AND entity_id = %s::uuid)
           OR detail->>'change_id' = %s
        ORDER BY at DESC, id
        """,
        (change_id, change_id),
    ).fetchall()
