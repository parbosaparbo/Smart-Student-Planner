"""
StudyMind AI — Local Persistence Manager
Saves and loads student profile, syllabus tree, schedule, and quiz history
so that progress is never lost when the browser is refreshed or closed.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict

DATA_DIR = Path(__file__).parent / "data"
STATE_FILE = DATA_DIR / "student_state.json"


def ensure_data_dir():
    """Ensure data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_persistent_state() -> Dict[str, Any]:
    """Load saved state from disk if available."""
    ensure_data_dir()
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_persistent_state(session_state: Dict[str, Any]) -> bool:
    """Save key session state fields to disk."""
    ensure_data_dir()
    keys_to_persist = [
        "student_profile",
        "topic_tree",
        "subject",
        "schedule",
        "quiz_results",
        "mock_evaluation",
        "mock_results",
        "daily_briefing",
        "weak_analysis",
        "flashcards",
        "gcal_event_map",
        "completed_revisions",
        "revision_history",
        "last_reschedule_result",
    ]
    data = {}
    for k in keys_to_persist:
        if k in session_state and session_state[k] is not None:
            data[k] = session_state[k]

    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception as e:
        print(f"Error saving state: {e}")
        return False


def clear_persistent_state() -> bool:
    """Clear saved state from disk."""
    if STATE_FILE.exists():
        try:
            os.remove(STATE_FILE)
            return True
        except Exception:
            return False
    return True

