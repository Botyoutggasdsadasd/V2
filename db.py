"""
SQLite database layer.
Tables:
  users(telegram_id, name, age, school, grade, track, ai_name, created_at)
  messages(id, telegram_id, role, content, created_at)   -- chat history for context + admin review
  ocr_cache(id, telegram_id, extracted_text, created_at) -- last OCR'd content, so buttons can act on it
"""
import os
import sqlite3
import time
from contextlib import contextmanager
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    name TEXT,
    age INTEGER,
    school TEXT,
    grade TEXT,
    track TEXT,
    ai_name TEXT,
    state TEXT DEFAULT 'idle',
    streak INTEGER DEFAULT 0,
    last_active_day TEXT,
    mood TEXT DEFAULT 'neutral',
    subject_counts TEXT DEFAULT '{}',
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER,
    role TEXT,       -- 'user' or 'assistant'
    content TEXT,
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS ocr_cache (
    telegram_id INTEGER PRIMARY KEY,
    extracted_text TEXT,
    created_at INTEGER
);
"""

@contextmanager
def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        # Lightweight migration for people upgrading from the earlier version of this bot
        existing_cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
        migrations = {
            "streak": "ALTER TABLE users ADD COLUMN streak INTEGER DEFAULT 0",
            "last_active_day": "ALTER TABLE users ADD COLUMN last_active_day TEXT",
            "mood": "ALTER TABLE users ADD COLUMN mood TEXT DEFAULT 'neutral'",
            "subject_counts": "ALTER TABLE users ADD COLUMN subject_counts TEXT DEFAULT '{}'",
        }
        for col, ddl in migrations.items():
            if col not in existing_cols:
                conn.execute(ddl)

def upsert_user(telegram_id, **fields):
    with get_conn() as conn:
        cur = conn.execute("SELECT telegram_id FROM users WHERE telegram_id=?", (telegram_id,))
        exists = cur.fetchone()
        if exists:
            cols = ", ".join(f"{k}=?" for k in fields)
            conn.execute(f"UPDATE users SET {cols} WHERE telegram_id=?",
                         (*fields.values(), telegram_id))
        else:
            fields["telegram_id"] = telegram_id
            fields["created_at"] = int(time.time())
            cols = ", ".join(fields.keys())
            qs = ", ".join("?" for _ in fields)
            conn.execute(f"INSERT INTO users ({cols}) VALUES ({qs})", tuple(fields.values()))

def get_user(telegram_id):
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
        row = cur.fetchone()
        return dict(row) if row else None

def set_state(telegram_id, state):
    upsert_user(telegram_id, state=state)

def save_message(telegram_id, role, content):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (telegram_id, role, content, created_at) VALUES (?,?,?,?)",
            (telegram_id, role, content, int(time.time())),
        )

def get_recent_history(telegram_id, limit=12):
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT role, content FROM messages WHERE telegram_id=? ORDER BY id DESC LIMIT ?",
            (telegram_id, limit),
        )
        rows = [dict(r) for r in cur.fetchall()]
        return list(reversed(rows))


# ---------------- Personality / memory helpers ----------------

import json
import datetime

def record_activity_and_streak(telegram_id):
    """Call once per incoming message. Bumps the daily study streak."""
    today = datetime.date.today().isoformat()
    user = get_user(telegram_id)
    if not user:
        return 0
    last_day = user.get("last_active_day")
    streak = user.get("streak") or 0
    if last_day == today:
        pass  # already counted today
    elif last_day == (datetime.date.today() - datetime.timedelta(days=1)).isoformat():
        streak += 1
    else:
        streak = 1
    upsert_user(telegram_id, streak=streak, last_active_day=today)
    return streak

def track_subject_mention(telegram_id, subject_key):
    user = get_user(telegram_id)
    if not user:
        return
    counts = {}
    try:
        counts = json.loads(user.get("subject_counts") or "{}")
    except Exception:
        counts = {}
    counts[subject_key] = counts.get(subject_key, 0) + 1
    upsert_user(telegram_id, subject_counts=json.dumps(counts))

def get_top_subjects(telegram_id, n=3):
    user = get_user(telegram_id)
    if not user:
        return []
    try:
        counts = json.loads(user.get("subject_counts") or "{}")
    except Exception:
        counts = {}
    return sorted(counts.items(), key=lambda x: -x[1])[:n]

def set_mood(telegram_id, mood):
    upsert_user(telegram_id, mood=mood)

def save_ocr(telegram_id, text):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO ocr_cache (telegram_id, extracted_text, created_at) VALUES (?,?,?) "
            "ON CONFLICT(telegram_id) DO UPDATE SET extracted_text=excluded.extracted_text, created_at=excluded.created_at",
            (telegram_id, text, int(time.time())),
        )

def get_ocr(telegram_id):
    with get_conn() as conn:
        cur = conn.execute("SELECT extracted_text FROM ocr_cache WHERE telegram_id=?", (telegram_id,))
        row = cur.fetchone()
        return row["extracted_text"] if row else None

def all_users():
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM users ORDER BY created_at DESC")
        return [dict(r) for r in cur.fetchall()]

def user_count():
    with get_conn() as conn:
        cur = conn.execute("SELECT COUNT(*) c FROM users")
        return cur.fetchone()["c"]
