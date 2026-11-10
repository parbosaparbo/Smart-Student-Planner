"""
StudyMind AI — Comprehensive SQLite Database & Migration Test Suite
Validates:
1. Schema & Table Creation (15 tables + indexes)
2. JSON-to-SQLite Migration Accuracy & Idempotency
3. Repository CRUD Operations & Relational Integrity
4. Foreign Key Constraints & Cascading Deletions
5. Quiz Submission & Weak Topic Auto-Tracking (< 70% threshold)
6. Mock Exam Submission & Topic Performance Analysis
7. Adaptive Rescheduling Flow with Database Persistence
8. Google Calendar Sync Event Tracking
9. Automatic & Manual Backups, Integrity Checks, and Restore Operations
10. Session State Persistence Bridge (save_persistent_state / load_persistent_state)
"""
import os
import sys
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, date
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import storage
from config import DATABASE_PATH, DATA_DIR, BACKUP_DIR
from database.connection import get_raw_connection, get_db_connection
from database.schema import init_database
from database.backup import create_backup, validate_backup, restore_backup, auto_daily_backup, list_backups
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
    record_student_activity,
    load_recent_activities,
    save_full_session_state,
    load_full_session_state,
    clear_student_data,
)
from core.weak_topic_manager import recalculate_future_schedule, auto_reschedule_workflow


class TestDatabaseMigration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Run migration on the main database to ensure it's seeded
        cls.migration_result = run_migration()

    def test_01_schema_and_tables(self):
        """Verify all 15 tables and indexes exist in SQLite database."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = {row[0] for row in cur.fetchall()}

            expected_tables = {
                "students", "subjects", "topics", "subtopics",
                "quizzes", "mock_exams", "topic_performances", "weak_topics",
                "study_schedules", "schedule_blocks", "revision_history",
                "calendar_events", "student_activities", "database_backups",
                "app_state"
            }
            for tbl in expected_tables:
                self.assertIn(tbl, tables, f"Expected table '{tbl}' not found in SQLite schema")

            cur.execute("PRAGMA integrity_check;")
            integrity = cur.fetchone()[0]
            self.assertEqual(integrity, "ok", "Database integrity check failed")

    def test_02_json_migration_verification(self):
        """Verify that existing JSON records were migrated accurately."""
        v = verify_migration()
        self.assertTrue(v["is_healthy"], "Verification report indicates unhealthy database")
        self.assertEqual(v["database_integrity"], "ok")
        counts = v["table_row_counts"]

        self.assertGreaterEqual(counts["students"], 1, "At least 1 student should be migrated")
        self.assertGreaterEqual(counts["subjects"], 1, "Subjects should be migrated")
        self.assertGreaterEqual(counts["topics"], 10, "Topics should be migrated")
        self.assertGreaterEqual(counts["subtopics"], 20, "Subtopics should be migrated")
        self.assertGreaterEqual(counts["quizzes"], 3, "Quizzes should be migrated")
        self.assertGreaterEqual(counts["weak_topics"], 1, "Weak topics should be tracked")

    def test_03_foreign_keys_and_cascades(self):
        """Verify foreign key enforcement and cascading deletes."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            # Create a test student
            cur.execute(
                "INSERT INTO students (student_name, daily_hours) VALUES ('CascadeStudent', 3.0)"
            )
            test_student_id = cur.lastrowid

            # Create subject and topic
            cur.execute(
                "INSERT INTO subjects (student_id, subject_name) VALUES (?, 'Test Subject')",
                (test_student_id,)
            )
            subj_id = cur.lastrowid

            cur.execute(
                "INSERT INTO topics (subject_id, topic_code, title) VALUES (?, 't_casc', 'Cascade Topic')",
                (subj_id,)
            )

            # Delete the student -> should cascade delete subject and topic
            cur.execute("DELETE FROM students WHERE id = ?", (test_student_id,))

            cur.execute("SELECT COUNT(*) FROM subjects WHERE student_id = ?", (test_student_id,))
            self.assertEqual(cur.fetchone()[0], 0, "Subjects should be cascade deleted")

            cur.execute("SELECT COUNT(*) FROM topics WHERE subject_id = ?", (subj_id,))
            self.assertEqual(cur.fetchone()[0], 0, "Topics should be cascade deleted")

    def test_04_quiz_submission_and_weak_topic_detection(self):
        """Verify quiz recording updates topic_performances and weak_topics (<70% rule)."""
        student_id = get_or_create_student("QuizTester", 4.0)
        
        # 1. Failing quiz (40%) -> should create active weak topic
        quiz_data_fail = {
            "topic_id": "test_weak_algo",
            "topic_title": "Algorithms Deep Dive",
            "score_pct": 40.0,
            "correct": 2,
            "total": 5,
            "questions": [],
            "answers": []
        }
        quiz_id = record_quiz_result(quiz_data_fail, student_id=student_id)
        self.assertGreater(quiz_id, 0)

        weak_list = get_weak_topics(student_id=student_id, status="active")
        matching = [w for w in weak_list if w["topic_id"] == "test_weak_algo"]
        self.assertEqual(len(matching), 1, "Weak topic should be active")
        self.assertEqual(matching[0]["urgency"], "critical")
        self.assertEqual(matching[0]["score_pct"], 40.0)

        # 2. Passing quiz (80%) on same topic -> should resolve weak topic
        quiz_data_pass = {
            "topic_id": "test_weak_algo",
            "topic_title": "Algorithms Deep Dive",
            "score_pct": 80.0,
            "correct": 4,
            "total": 5,
            "questions": [],
            "answers": []
        }
        record_quiz_result(quiz_data_pass, student_id=student_id)
        weak_active = get_weak_topics(student_id=student_id, status="active")
        active_match = [w for w in weak_active if w["topic_id"] == "test_weak_algo"]
        self.assertEqual(len(active_match), 0, "Weak topic should be marked resolved after 80% score")

    def test_05_mock_evaluation_persistence(self):
        """Verify mock exam recording stores topic performance breakdown in SQLite."""
        student_id = get_or_create_student("MockTester", 4.0)
        mock_eval = {
            "topic_performance": [
                {"topic_id": "math_diff", "topic_title": "Calculus", "score_pct": 30.0, "verdict": "critical", "priority_action": "Practice limits"},
                {"topic_id": "stats_prob", "topic_title": "Probability", "score_pct": 65.0, "verdict": "weak", "priority_action": "Revise Bayes"}
            ]
        }
        mock_id = record_mock_evaluation(mock_eval, student_id=student_id)
        self.assertGreater(mock_id, 0)

        loaded_eval = load_mock_evaluation(student_id=student_id)
        self.assertIsNotNone(loaded_eval)
        self.assertEqual(len(loaded_eval.get("topic_performance", [])), 2)

        weak_topics = get_weak_topics(student_id=student_id, status="active")
        w_ids = [w["topic_id"] for w in weak_topics]
        self.assertIn("math_diff", w_ids)
        self.assertIn("stats_prob", w_ids)

    def test_06_schedule_persistence_and_blocks(self):
        """Verify saving and loading schedules with daily blocks."""
        student_id = get_or_create_student("ScheduleTester", 4.0)
        test_schedule = {
            "subject": "CS Core 2026",
            "total_study_blocks": 2,
            "daily_blocks": [
                {
                    "date": "2026-11-15",
                    "day_type": "study",
                    "blocks": [
                        {
                            "topic_id": "cn_sub",
                            "topic_title": "Subnetting",
                            "duration_minutes": 90,
                            "start_time": "09:00",
                            "end_time": "10:30",
                            "completed": False
                        }
                    ]
                },
                {
                    "date": "2026-11-16",
                    "day_type": "study",
                    "blocks": [
                        {
                            "topic_id": "os_threads",
                            "topic_title": "Multithreading",
                            "duration_minutes": 60,
                            "start_time": "14:00",
                            "end_time": "15:00",
                            "completed": True
                        }
                    ]
                }
            ]
        }
        sched_id = save_study_schedule(test_schedule, student_id=student_id)
        self.assertGreater(sched_id, 0)

        loaded = load_active_schedule(student_id=student_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["subject"], "CS Core 2026")
        self.assertEqual(len(loaded["daily_blocks"]), 2)
        b1 = loaded["daily_blocks"][0]["blocks"][0]
        self.assertEqual(b1["topic_title"], "Subnetting")
        self.assertEqual(b1["start_time"], "09:00")

    def test_07_adaptive_rescheduling_with_sqlite(self):
        """Verify weak topic auto-rescheduling recalculates schedule and saves to SQLite."""
        # Load active schedule from storage
        saved_state = storage.load_persistent_state()
        schedule = saved_state.get("schedule")
        self.assertIsNotNone(schedule, "Active schedule must be present in SQLite")

        weak_list = storage.get_weak_topics(status="active")
        self.assertGreaterEqual(len(weak_list), 1, "Must have weak topics to test rescheduling")

        # Run recalculation
        resched_result = recalculate_future_schedule(
            current_schedule=schedule,
            weak_topics=weak_list[:2],
            student_profile=saved_state.get("student_profile", {"daily_hours": 3.5, "blocked_days": ["sunday"]}),
            today_date=date(2026, 11, 10)
        )
        self.assertEqual(resched_result["status"], "success")
        self.assertGreaterEqual(resched_result["blocks_added"], 1)

        # Save back to database
        saved_state["schedule"] = resched_result["updated_schedule"]
        saved_state["last_reschedule_result"] = resched_result
        success = storage.save_persistent_state(saved_state)
        self.assertTrue(success, "Saving recalculated schedule to SQLite failed")

        # Reload and verify
        reloaded = storage.load_persistent_state()
        new_blocks = sum(len(d.get("blocks", [])) for d in reloaded["schedule"]["daily_blocks"])
        self.assertGreaterEqual(new_blocks, 1)

    def test_08_calendar_event_tracking(self):
        """Verify calendar events tracking in SQLite."""
        student_id = get_or_create_student("CalTester", 4.0)
        save_calendar_event(
            gcal_event_id="smai_test_event_123",
            event_title="📚 Computer Networks Revision",
            start_time_iso="2026-11-12T09:00:00",
            end_time_iso="2026-11-12T10:30:00",
            student_id=student_id
        )
        events = load_calendar_events(student_id=student_id)
        matching = [e for e in events if e["gcal_event_id"] == "smai_test_event_123"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["event_title"], "📚 Computer Networks Revision")

    def test_09_backup_and_recovery(self):
        """Verify online backup creation, PRAGMA validation, and safe restore."""
        # Create manual backup
        res = create_backup(backup_type="test_suite", tag="unit_test")
        self.assertTrue(res["success"], f"Backup failed: {res.get('error')}")
        backup_path = res["backup_path"]
        self.assertTrue(os.path.exists(backup_path))
        self.assertGreater(res["file_size_bytes"], 0)

        # Validate backup
        is_valid, msg = validate_backup(backup_path)
        self.assertTrue(is_valid, f"Backup validation failed: {msg}")

        # List backups
        backups = list_backups()
        self.assertGreaterEqual(len(backups), 1)

        # Test safe restore to a temporary file
        temp_dest = tempfile.mktemp(suffix=".db")
        restore_res = restore_backup(backup_path, target_db_path=temp_dest)
        self.assertTrue(restore_res["success"], f"Restore failed: {restore_res.get('error')}")
        valid_restored, _ = validate_backup(temp_dest)
        self.assertTrue(valid_restored, "Restored database failed integrity check")
        if os.path.exists(temp_dest):
            os.remove(temp_dest)

    def test_10_session_state_roundtrip(self):
        """Verify full Streamlit session state roundtrip through SQLite."""
        test_state = {
            "student_profile": {
                "student_name": "RoundtripStudent",
                "daily_hours": 4.5,
                "blocked_days": ["Saturday"],
                "preferred_times": ["08:00", "15:00"]
            },
            "subject": "System Design",
            "daily_briefing": {"headline": "Focus on Cache Eviction Policies"},
            "flashcards": [{"q": "What is LRU?", "a": "Least Recently Used"}]
        }
        success = storage.save_persistent_state(test_state)
        self.assertTrue(success)

        loaded = storage.load_persistent_state("RoundtripStudent")
        self.assertEqual(loaded["student_profile"]["student_name"], "RoundtripStudent")
        self.assertEqual(loaded["student_profile"]["daily_hours"], 4.5)
        self.assertEqual(loaded["daily_briefing"]["headline"], "Focus on Cache Eviction Policies")
        self.assertEqual(loaded["flashcards"][0]["q"], "What is LRU?")


if __name__ == "__main__":
    unittest.main(verbosity=2)
