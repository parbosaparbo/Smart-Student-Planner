"""
StudyMind AI — Database Package
Normalized SQLite primary database and hybrid storage subsystem.
"""
from database.connection import get_db_connection, get_raw_connection
from database.schema import init_database
from database.backup import create_backup, auto_daily_backup, validate_backup, restore_backup, list_backups
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
from database.migration import run_migration, verify_migration

__all__ = [
    "get_db_connection",
    "get_raw_connection",
    "init_database",
    "create_backup",
    "auto_daily_backup",
    "validate_backup",
    "restore_backup",
    "list_backups",
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
    "save_full_session_state",
    "load_full_session_state",
    "clear_student_data",
    "run_migration",
    "verify_migration",
]

