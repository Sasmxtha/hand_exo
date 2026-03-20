-- Hand Rehabilitation Sorting Game — Database Schema
-- Author: S. Sasmitha
--
-- Usage:
--   mysql -u root -p < docs/schema.sql
--
-- Or paste into MySQL Workbench / phpMyAdmin.

CREATE DATABASE IF NOT EXISTS rehab_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE rehab_db;

-- ── Players ───────────────────────────────────────────────────────────────────
-- Stores long-term per-player aggregate statistics.
-- KPI: avg_score = total_score / games_played
CREATE TABLE IF NOT EXISTS players (
    player_id    INT          NOT NULL AUTO_INCREMENT,
    player_name  VARCHAR(100) NOT NULL,
    total_score  INT          NOT NULL DEFAULT 0,
    games_played INT          NOT NULL DEFAULT 0,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (player_id),
    UNIQUE KEY uq_player_name (player_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Game Sessions ─────────────────────────────────────────────────────────────
-- One row per gameplay session.
-- KPI: accuracy = objects_collected / total_attempts  (stored as 0.0–1.0)
CREATE TABLE IF NOT EXISTS game_sessions (
    session_id   INT          NOT NULL AUTO_INCREMENT,
    player_name  VARCHAR(100) NOT NULL,
    score        INT          NOT NULL DEFAULT 0,
    accuracy     FLOAT        NOT NULL DEFAULT 0.0   COMMENT '0.0 – 1.0',
    duration_sec INT          NOT NULL DEFAULT 0,
    started_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at     DATETIME,
    PRIMARY KEY (session_id),
    FOREIGN KEY fk_player (player_name)
        REFERENCES players(player_name)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Useful views ──────────────────────────────────────────────────────────────

-- Per-player leaderboard
CREATE OR REPLACE VIEW v_leaderboard AS
SELECT
    player_name,
    total_score,
    games_played,
    ROUND(total_score / NULLIF(games_played, 0), 1) AS avg_score
FROM players
ORDER BY avg_score DESC;

-- Recent sessions (last 10 per player)
CREATE OR REPLACE VIEW v_recent_sessions AS
SELECT
    gs.session_id,
    gs.player_name,
    gs.score,
    ROUND(gs.accuracy * 100, 1)  AS accuracy_pct,
    gs.duration_sec,
    gs.started_at
FROM game_sessions gs
ORDER BY gs.session_id DESC
LIMIT 10;
