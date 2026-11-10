"""
StudyMind AI — Configuration & Constants
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Gemini ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

# ── App metadata ──────────────────────────────────────────────────────────────
APP_TITLE       = "StudyMind AI"
APP_ICON        = "🧠"
APP_SUBTITLE    = "Your intelligent academic coach — powered by Gemini"

# ── Thresholds ────────────────────────────────────────────────────────────────
MASTERY_THRESHOLD    = 70   # below this → auto-reschedule
QUIZ_TIME_PER_Q      = 75   # seconds per question (default)
MIN_REST_DAYS_PER_WEEK = 1

# ── Schedule distribution ─────────────────────────────────────────────────────
NEW_TOPICS_PCT    = 0.70
WEAK_TOPICS_PCT   = 0.20
MOCK_REVISION_PCT = 0.10

# ── UI colours ────────────────────────────────────────────────────────────────
COLORS = {
    "primary":   "#6C63FF",
    "success":   "#2ECC71",
    "warning":   "#F39C12",
    "danger":    "#E74C3C",
    "info":      "#3498DB",
    "bg_dark":   "#0E1117",
    "card_bg":   "#1A1D23",
    "text_muted":"#8A8F9B",
}

# ── Difficulty labels ─────────────────────────────────────────────────────────
DIFFICULTY_LABELS = {
    1: "Recall",
    2: "Understand",
    3: "Apply",
    4: "Analyze",
    5: "Synthesize",
}

URGENCY_COLORS = {
    "critical": COLORS["danger"],
    "high":     COLORS["warning"],
    "medium":   COLORS["info"],
}

# ── Database & Hybrid Storage ──────────────────────────────────────────────────
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "studymind.db")))
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", str(DATA_DIR / "backups")))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH.as_posix()}")
