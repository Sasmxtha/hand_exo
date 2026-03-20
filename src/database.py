"""
database.py
Author: S. Sasmitha

MySQL analytics layer — stores session data and generates adaptive feedback.

Paper (Section III-E / Table III):
  Tables:
    players      — long-term aggregates (total_score, games_played)
    game_sessions — per-session metrics (score, accuracy, duration_sec)

  KPIs:
    avg_score = total_score / games_played
    accuracy  = objects_collected / (objects_collected + objects_missed)

  Adaptive feedback tiers:
    < 50%   → Beginner     (basic timing, hand positioning)
    50–75%  → Intermediate (speed, pick-up/drop consistency)
    > 75%   → Advanced     (gesture-timing synchronisation)
"""

from __future__ import annotations
import datetime
from typing import Optional, Dict

try:
    import mysql.connector
    _MYSQL_OK = True
except ImportError:
    _MYSQL_OK = False

from src.config import DB as _DB

_DDL_PLAYERS = """
CREATE TABLE IF NOT EXISTS players (
    player_id    INT          AUTO_INCREMENT PRIMARY KEY,
    player_name  VARCHAR(100) NOT NULL UNIQUE,
    total_score  INT          DEFAULT 0,
    games_played INT          DEFAULT 0,
    created_at   DATETIME     DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

_DDL_SESSIONS = """
CREATE TABLE IF NOT EXISTS game_sessions (
    session_id   INT          AUTO_INCREMENT PRIMARY KEY,
    player_name  VARCHAR(100) NOT NULL,
    score        INT          DEFAULT 0,
    accuracy     FLOAT        DEFAULT 0.0 COMMENT '0.0–1.0',
    duration_sec INT          DEFAULT 0,
    started_at   DATETIME     DEFAULT CURRENT_TIMESTAMP,
    ended_at     DATETIME,
    FOREIGN KEY (player_name)
        REFERENCES players(player_name)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


class DatabaseManager:

    def __init__(self):
        self._conn   = None
        self._cursor = None
        self._connect()

    # ── Connection ─────────────────────────────────────────────────────────────

    def _connect(self):
        if not _MYSQL_OK:
            return
        try:
            self._conn = mysql.connector.connect(
                host=_DB.HOST, user=_DB.USER,
                password=_DB.PASS, database=_DB.NAME
            )
            self._cursor = self._conn.cursor()
            self._cursor.execute(_DDL_PLAYERS)
            self._cursor.execute(_DDL_SESSIONS)
            self._conn.commit()
        except Exception as e:
            print(f"[DB] {e}")
            self._conn = self._cursor = None

    def _exec(self, sql: str, params: tuple = ()):
        if not self._cursor:
            return
        try:
            self._cursor.execute(sql, params)
            self._conn.commit()
        except Exception as e:
            print(f"[DB] exec error: {e}")

    # ── Player ─────────────────────────────────────────────────────────────────

    def ensure_player(self, name: str):
        self._exec(
            "INSERT IGNORE INTO players (player_name) VALUES (%s)", (name,)
        )

    def get_player_stats(self, name: str) -> Optional[Dict]:
        if not self._cursor:
            return None
        try:
            self._cursor.execute(
                "SELECT total_score, games_played FROM players "
                "WHERE player_name=%s", (name,)
            )
            row = self._cursor.fetchone()
            if not row:
                return None
            ts, gp = row
            return {"total_score": ts, "games_played": gp,
                    "avg_score": ts / gp if gp else 0}
        except Exception:
            return None

    # ── Session ────────────────────────────────────────────────────────────────

    def start_session(self, name: str) -> Optional[int]:
        if not self._cursor:
            return None
        try:
            self._cursor.execute(
                "INSERT INTO game_sessions (player_name, started_at) "
                "VALUES (%s, %s)",
                (name, datetime.datetime.now())
            )
            self._conn.commit()
            return self._cursor.lastrowid
        except Exception:
            return None

    def end_session(self, session_id: int, score: int,
                    accuracy: float, duration_sec: int):
        if not session_id:
            return
        self._exec(
            "UPDATE game_sessions "
            "SET score=%s, accuracy=%s, duration_sec=%s, ended_at=%s "
            "WHERE session_id=%s",
            (score, accuracy, duration_sec, datetime.datetime.now(), session_id)
        )
        self._exec(
            "UPDATE players "
            "SET total_score=total_score+%s, games_played=games_played+1 "
            "WHERE player_name=("
            "  SELECT player_name FROM game_sessions WHERE session_id=%s)",
            (score, session_id)
        )

    # ── Analytics & adaptive feedback (Section III-E) ──────────────────────────

    def get_recent_accuracy(self, name: str, n: int = 3) -> float:
        if not self._cursor:
            return 0.0
        try:
            self._cursor.execute(
                "SELECT accuracy FROM game_sessions "
                "WHERE player_name=%s ORDER BY session_id DESC LIMIT %s",
                (name, n)
            )
            rows = self._cursor.fetchall()
            return sum(r[0] for r in rows) / len(rows) if rows else 0.0
        except Exception:
            return 0.0

    def get_adaptive_feedback(self, name: str) -> str:
        """
        Three-tier adaptive feedback as described in paper Section III-E.
        """
        acc = self.get_recent_accuracy(name)
        if acc < _DB.BEG_THRESH:
            return (
                "Beginner level — accuracy below 50%. "
                "Focus on hand positioning: align your hand over the correct "
                "basket before releasing."
            )
        elif acc < _DB.INT_THRESH:
            return (
                "Intermediate level — accuracy 50–75%. "
                "Work on pick-up and drop consistency: practise smooth "
                "open/close transitions."
            )
        return (
            "Advanced level — excellent! "
            "Work on gesture-timing synchronisation for higher scores."
        )

    def close(self):
        if self._cursor:
            self._cursor.close()
        if self._conn:
            self._conn.close()
