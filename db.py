import sqlite3
from typing import Optional

DB_PATH = "slack_tokens.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_tokens (
            user_id TEXT PRIMARY KEY,
            access_token TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def save_user_token(user_id: str, access_token: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO user_tokens(user_id, access_token)
        VALUES(?, ?)
        ON CONFLICT(user_id) DO UPDATE SET access_token=excluded.access_token
    """, (user_id, access_token))
    conn.commit()
    conn.close()

def get_user_token(user_id: str) -> Optional[str]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT access_token FROM user_tokens WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None
