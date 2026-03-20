"""
config.py — Central configuration for hand_exo
Author: S. Sasmitha
All constants exactly match the paper's implementation details.
"""
from dataclasses import dataclass, field
from typing import Tuple
import os

# ── Game (Section III-C) ──────────────────────────────────────────────────────
@dataclass
class GameConfig:
    SCREEN_W: int   = 1280
    SCREEN_H: int   = 720
    FPS:      int   = 60
    LIVES:    int   = 5
    POINTS:   int   = 10          # correct placement
    SPAWN_SEC: float = 3.0        # base spawn interval
    SPAWN_MIN: float = 0.5
    SPAWN_MAX: float = 2.0
    FRAME_BUDGET_MS: int = 33     # 30 FPS processing budget

    # Colours
    SKY:    Tuple = (135, 206, 235)
    WHITE:  Tuple = (255, 255, 255)
    BLACK:  Tuple = (0,   0,   0)
    RED:    Tuple = (220, 50,  50)
    GREEN:  Tuple = (0,   200, 0)
    BLUE:   Tuple = (50,  50,  200)
    YELLOW: Tuple = (255, 200, 0)
    PURPLE: Tuple = (120, 50,  200)

    # Input modes
    MODE_VISION: str = "VISION"
    MODE_GLOVE:  str = "GLOVE"

# ── Camera (Section III-A) ────────────────────────────────────────────────────
@dataclass
class CameraConfig:
    # Camera 0 → Logitech C920 → object tracking
    # Camera 1 → Microsoft LifeCam → hand gesture
    CAM_TRACKER:  int   = 0
    CAM_GESTURE:  int   = 1
    WIDTH:        int   = 1280
    HEIGHT:       int   = 720
    FPS:          int   = 30
    TAU_OPEN:     float = 0.25    # Euclidean distance threshold (normalised)
    DETECT_CONF:  float = 0.70
    TRACK_CONF:   float = 0.50
    CSRT_RECOVER: float = 1.2     # seconds before auto-reinitialise
    CALIB_PATH:   str   = "calibration_matrix.npy"

# ── Glove (Section III-D) ─────────────────────────────────────────────────────
@dataclass
class GloveConfig:
    BAUD:       int   = 9600
    OPEN_DEG:   int   = 0
    CLOSE_DEG:  int   = 90
    MAX_DEG:    int   = 90
    RATE_DPS:   int   = 45        # software rate limit
    WATCHDOG_S: float = 2.0
    INIT_DELAY: float = 2.0       # Arduino reset time after USB connect

# ── Voice (Section III-A) ─────────────────────────────────────────────────────
@dataclass
class VoiceConfig:
    MODEL:       str   = "vosk-model-small-en-us-0.15"
    SAMPLE_RATE: int   = 16_000
    BLOCK_SIZE:  int   = 8_000
    COMMANDS:    Tuple = ("open", "close", "stop")

# ── Database (Section III-E) ──────────────────────────────────────────────────
@dataclass
class DBConfig:
    HOST: str = os.getenv("REHAB_DB_HOST",     "localhost")
    USER: str = os.getenv("REHAB_DB_USER",     "rehab_user")
    PASS: str = os.getenv("REHAB_DB_PASSWORD", "rehab_pass")
    NAME: str = os.getenv("REHAB_DB_NAME",     "rehab_db")
    BEG_THRESH: float = 0.50     # < 50% → beginner
    INT_THRESH: float = 0.75     # 50-75% → intermediate, >75% → advanced

# ── EMG (Section IV-D) ────────────────────────────────────────────────────────
@dataclass
class EMGConfig:
    FS:         int   = 1000     # Hz
    BP_LO:      int   = 20       # Hz
    BP_HI:      int   = 450      # Hz
    NOTCH:      int   = 50       # Hz power-line
    NOTCH_Q:    float = 30.0
    RMS_WIN_MS: int   = 50
    N_CH:       int   = 8
    LABELS: Tuple = (
        "Brachioradialis",
        "Extensor Carpi Ulnaris",
        "Tendon of Biceps Brachii",
        "Flexor Digitorum Superficialis",
        "Extensor Digitorum",
        "Flexor Carpi Radialis",
        "Pronator Teres",
        "Anconeus",
    )

# ── Singleton instances ───────────────────────────────────────────────────────
GAME  = GameConfig()
CAM   = CameraConfig()
GLOVE = GloveConfig()
VOICE = VoiceConfig()
DB    = DBConfig()
EMG   = EMGConfig()
