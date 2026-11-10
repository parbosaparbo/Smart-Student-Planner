"""
StudyMind AI — Local Storage & Persistence Service
Unified Hybrid Storage Layer:
- SQLite is the single source of truth for persistent student profiles, syllabi,
  schedules, quiz history, mock exams, weak spots, calendar events, and activities.
- JSON handles lightweight caching (AI quiz/schedule caches) and configuration.
- Maintains 100% backward compatibility for all existing Streamlit pages and engines
  via load_persistent_state(), save_persistent_state(), and clear_persistent_state().
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

from config import DATA_DIR, DATABASE_PATH, BACKUP_DIR
from database.connection import get_db_connection, ensure_db_dir
from database.schema import init_database
from database.backup import create_backup, auto_daily_backup, validate_backup, restore_backup, list_backups
from database.migration import run_migration, verify_migration
from database.repository import (
    get_or_create_student,
    get_student_profile,
    save_syllabus_tree,
    load_syllabus_tree,
    save_study_schedule,
    load_active_schedule,
    record_quiz_result,
    load_quiz_results,
    record_mock_evaluation,
    load_mock_evaluation,
    get_weak_topics,
    save_calendar_event,
    load_calendar_events,
    delete_calendar_event,
    save_oauth_token,
    load_oauth_token,
    delete_oauth_token,
    set_app_state,
    get_app_state,
    record_student_activity,
    load_recent_activities,
    save_full_session_state,
    load_full_session_state,
    clear_student_data,
)

logger = logging.getLogger(__name__)

STATE_FILE = DATA_DIR / "student_state.json"


def ensure_storage_ready() -> None:
    """Ensure data directory, SQLite database, and schema are ready."""
    ensure_db_dir()
    # Check if database file exists and has tables
    if not DATABASE_PATH.exists() or DATABASE_PATH.stat().st_size == 0:
        logger.info("Initializing SQLite database on first use...")
        with get_db_connection() as conn:
            init_database(conn)
        if STATE_FILE.exists():
            logger.info("Existing student_state.json detected; migrating to SQLite...")
            run_migration()


def load_persistent_state(student_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Load saved state from SQLite as the single source of truth.
    Performs daily auto-backup on first load of the day.
    """
    ensure_storage_ready()
    # Auto daily backup if not already taken today
    try:
        auto_daily_backup()
    except Exception as e:
        logger.warning(f"Auto daily backup warning: {e}")

    state = load_full_session_state(student_name=student_name)
    if not state and STATE_FILE.exists():
        # Fallback migration if DB was empty but JSON exists
        run_migration()
        state = load_full_session_state(student_name=student_name)

    return state or {}


def save_persistent_state(session_state: Dict[str, Any]) -> bool:
    """
    Save session state into SQLite primary database transactionally.
    """
    ensure_storage_ready()
    success = save_full_session_state(session_state)
    
    # Keep a secondary backup copy of student_state.json for safety
    try:
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
        data = {k: session_state[k] for k in keys_to_persist if k in session_state and session_state[k] is not None}
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        logger.warning(f"Secondary JSON backup sync warning: {e}")

    return success


def clear_persistent_state(student_id: int = 1) -> bool:
    """Clear saved student state from SQLite and disk."""
    success = clear_student_data(student_id=student_id)
    if STATE_FILE.exists():
        try:
            os.remove(STATE_FILE)
        except Exception:
            pass
    return success


# Re-export all database functions for modules that prefer direct repository access
__all__ = [
    "load_persistent_state",
    "save_persistent_state",
    "clear_persistent_state",
    "ensure_storage_ready",
    "get_or_create_student",
    "get_student_profile",
    "save_syllabus_tree",
    "load_syllabus_tree",
    "save_study_schedule",
    "load_active_schedule",
    "record_quiz_result",
    "load_quiz_results",
    "record_mock_evaluation",
    "load_mock_evaluation",
    "get_weak_topics",
    "save_calendar_event",
    "load_calendar_events",
    "delete_calendar_event",
    "save_oauth_token",
    "load_oauth_token",
    "delete_oauth_token",
    "set_app_state",
    "get_app_state",
    "record_student_activity",
    "load_recent_activities",
    "create_backup",
    "auto_daily_backup",
    "validate_backup",
    "restore_backup",
    "list_backups",
    "run_migration",
    "verify_migration",
]
