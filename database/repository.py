"""
StudyMind AI — Database Repository Layer
Provides strongly typed, normalized data access for students, subjects, topics,
schedules, quizzes, mock exams, weak topics, calendar events, and activity logs.
Maintains 100% data compatibility with existing Streamlit session state and engines.
"""
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import logging

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from database.connection import get_db_connection, get_raw_connection

logger = logging.getLogger(__name__)


# ── Student Profile ──────────────────────────────────────────────────────────

def get_or_create_student(
    student_name: str = "TestStudent",
    daily_hours: float = 4.0,
    blocked_days: Optional[List[str]] = None,
    preferred_times: Optional[List[str]] = None,
    conn: Optional[sqlite3.Connection] = None
) -> int:
    """
    Get student ID by name, creating a new profile if it does not exist.
    Updates preferences if new ones are provided.
    """
    def _op(c: sqlite3.Connection) -> int:
        cur = c.cursor()
        cur.execute("SELECT id FROM students WHERE student_name = ?", (student_name,))
        row = cur.fetchone()
        if row:
            student_id = row[0]
            if blocked_days is not None or preferred_times is not None or daily_hours:
                cur.execute(
                    """
                    UPDATE students
                    SET daily_hours = COALESCE(?, daily_hours),
                        blocked_days = COALESCE(?, blocked_days),
                        preferred_times = COALESCE(?, preferred_times),
                        updated_at = datetime('now', 'localtime')
                    WHERE id = ?
                    """,
                    (
                        daily_hours,
                        json.dumps(blocked_days) if blocked_days is not None else None,
                        json.dumps(preferred_times) if preferred_times is not None else None,
                        student_id
                    )
                )
            return student_id
        
        # Create new student
        b_days = json.dumps(blocked_days or [])
        p_times = json.dumps(preferred_times or ["09:00", "14:00"])
        cur.execute(
            """
            INSERT INTO students (student_name, daily_hours, blocked_days, preferred_times)
            VALUES (?, ?, ?, ?)
            """,
            (student_name, daily_hours, b_days, p_times)
        )
        return cur.lastrowid

    if conn is not None:
        return _op(conn)
    with get_db_connection() as c:
        return _op(c)


def get_student_profile(
    student_id: Optional[int] = None,
    student_name: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> Optional[Dict[str, Any]]:
    """Retrieve student profile and preferences."""
    def _op(c: sqlite3.Connection):
        cur = c.cursor()
        if student_id:
            cur.execute("SELECT * FROM students WHERE id = ?", (student_id,))
        elif student_name:
            cur.execute("SELECT * FROM students WHERE student_name = ?", (student_name,))
        else:
            cur.execute("SELECT * FROM students ORDER BY id LIMIT 1")
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "student_name": row["student_name"],
            "daily_hours": float(row["daily_hours"]),
            "blocked_days": json.loads(row["blocked_days"] or "[]"),
            "preferred_times": json.loads(row["preferred_times"] or "[]"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }

    if conn is not None:
        return _op(conn)
    with get_db_connection() as c:
        return _op(c)


# ── Subjects & Syllabus Topics ───────────────────────────────────────────────

def save_syllabus_tree(
    topic_tree: Dict[str, Any],
    student_id: int = 1,
    conn: Optional[sqlite3.Connection] = None
) -> int:
    """
    Save complete syllabus tree (subject, topics, subtopics) into normalized tables.
    Returns the subject_id.
    """
    def _op(c: sqlite3.Connection) -> int:
        cur = c.cursor()
        subj_name = topic_tree.get("subject", "General Subject")
        exam_type = topic_tree.get("exam_type", "")
        has_electives = 1 if topic_tree.get("has_electives") else 0
        total_hours = float(topic_tree.get("total_estimated_hours", 0.0))
        sha256 = topic_tree.get("sha256", "")
        tier = topic_tree.get("tier_used", "")
        doc_metrics = json.dumps(topic_tree.get("document_metrics", {}))

        # Upsert subject
        cur.execute(
            """
            INSERT INTO subjects (student_id, subject_name, exam_type, has_electives, total_estimated_hours, sha256, tier_used, document_metrics)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(student_id, subject_name) DO UPDATE SET
                exam_type = excluded.exam_type,
                has_electives = excluded.has_electives,
                total_estimated_hours = excluded.total_estimated_hours,
                sha256 = excluded.sha256,
                tier_used = excluded.tier_used,
                document_metrics = excluded.document_metrics
            """,
            (student_id, subj_name, exam_type, has_electives, total_hours, sha256, tier, doc_metrics)
        )
        cur.execute("SELECT id FROM subjects WHERE student_id = ? AND subject_name = ?", (student_id, subj_name))
        subj_row = cur.fetchone()
        subject_id = subj_row["id"] if isinstance(subj_row, sqlite3.Row) else subj_row[0]

        # Insert topics and subtopics
        topics_list = topic_tree.get("topics", [])
        for topic in topics_list:
            t_code = str(topic.get("id", f"t_{topic.get('title', '')[:10]}"))
            t_title = topic.get("title", "Untitled Topic")
            t_diff = int(topic.get("difficulty", 3))
            t_prio = int(topic.get("priority", 3))
            t_hours = float(topic.get("estimated_hours", 0.0))
            is_elec = 1 if topic.get("is_elective") else 0
            elec_grp = topic.get("elective_group")
            prereqs = json.dumps(topic.get("prerequisites", []))

            cur.execute(
                """
                INSERT INTO topics (subject_id, topic_code, title, difficulty, priority, estimated_hours, is_elective, elective_group, prerequisites)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(subject_id, topic_code) DO UPDATE SET
                    title = excluded.title,
                    difficulty = excluded.difficulty,
                    priority = excluded.priority,
                    estimated_hours = excluded.estimated_hours,
                    is_elective = excluded.is_elective,
                    elective_group = excluded.elective_group,
                    prerequisites = excluded.prerequisites
                """,
                (subject_id, t_code, t_title, t_diff, t_prio, t_hours, is_elec, elec_grp, prereqs)
            )
            cur.execute("SELECT id FROM topics WHERE subject_id = ? AND topic_code = ?", (subject_id, t_code))
            t_row = cur.fetchone()
            topic_id = t_row["id"] if isinstance(t_row, sqlite3.Row) else t_row[0]

            # Subtopics
            subtopics_list = topic.get("subtopics", [])
            for st in subtopics_list:
                st_code = str(st.get("id", f"{t_code}_s"))
                st_title = st.get("title", "")
                st_hours = float(st.get("estimated_hours", 0.0))
                key_concepts = json.dumps(st.get("key_concepts", []))

                cur.execute(
                    """
                    INSERT INTO subtopics (topic_id, subtopic_code, title, estimated_hours, key_concepts)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(topic_id, subtopic_code) DO UPDATE SET
                        title = excluded.title,
                        estimated_hours = excluded.estimated_hours,
                        key_concepts = excluded.key_concepts
                    """,
                    (topic_id, st_code, st_title, st_hours, key_concepts)
                )

        return subject_id

    if conn is not None:
        return _op(conn)
    with get_db_connection() as c:
        return _op(c)


def load_syllabus_tree(
    subject_name: Optional[str] = None,
    student_id: int = 1,
    conn: Optional[sqlite3.Connection] = None
) -> Optional[Dict[str, Any]]:
    """
    Load normalized syllabus tree from SQLite into standard StudyMind topic_tree dictionary.
    """
    def _op(c: sqlite3.Connection):
        cur = c.cursor()
        if subject_name:
            cur.execute("SELECT * FROM subjects WHERE student_id = ? AND subject_name = ?", (student_id, subject_name))
        else:
            cur.execute("SELECT * FROM subjects WHERE student_id = ? ORDER BY id DESC LIMIT 1", (student_id,))
        subj = cur.fetchone()
        if not subj:
            return None

        subject_id = subj["id"]
        # Fetch topics
        cur.execute("SELECT * FROM topics WHERE subject_id = ? ORDER BY id ASC", (subject_id,))
        topic_rows = cur.fetchall()

        topics = []
        for tr in topic_rows:
            tid = tr["id"]
            # Fetch subtopics
            cur.execute("SELECT * FROM subtopics WHERE topic_id = ? ORDER BY id ASC", (tid,))
            sub_rows = cur.fetchall()
            subtopics = []
            for sr in sub_rows:
                subtopics.append({
                    "id": sr["subtopic_code"],
                    "title": sr["title"],
                    "estimated_hours": float(sr["estimated_hours"]),
                    "key_concepts": json.loads(sr["key_concepts"] or "[]")
                })

            topics.append({
                "id": tr["topic_code"],
                "title": tr["title"],
                "difficulty": tr["difficulty"],
                "priority": tr["priority"],
                "estimated_hours": float(tr["estimated_hours"]),
                "is_elective": bool(tr["is_elective"]),
                "elective_group": tr["elective_group"],
                "prerequisites": json.loads(tr["prerequisites"] or "[]"),
                "subtopics": subtopics
            })

        return {
            "subject": subj["subject_name"],
            "exam_type": subj["exam_type"],
            "has_electives": bool(subj["has_electives"]),
            "total_estimated_hours": float(subj["total_estimated_hours"]),
            "sha256": subj["sha256"],
            "tier_used": subj["tier_used"],
            "document_metrics": json.loads(subj["document_metrics"] or "{}"),
            "topics": topics
        }

    if conn is not None:
        return _op(conn)
    with get_db_connection() as c:
        return _op(c)


# ── Study Schedules & Daily Blocks ──────────────────────────────────────────

def save_study_schedule(
    schedule_dict: Dict[str, Any],
    student_id: int = 1,
    conn: Optional[sqlite3.Connection] = None
) -> int:
    """
    Save complete study schedule into study_schedules and schedule_blocks.
    Maintains 100% compatibility with daily_blocks format.
    """
    def _op(c: sqlite3.Connection) -> int:
        cur = c.cursor()
        subj = schedule_dict.get("subject", "General Schedule")
        daily_blocks = schedule_dict.get("daily_blocks", [])
        resched_summary = json.dumps(schedule_dict.get("reschedule_summary", {}))
        total_blocks = schedule_dict.get("total_study_blocks", 0)
        last_resched = schedule_dict.get("last_rescheduled_at")

        # Deactivate old schedules for this subject
        cur.execute(
            "UPDATE study_schedules SET is_active = 0 WHERE student_id = ? AND subject_name = ?",
            (student_id, subj)
        )

        # Insert new schedule
        cur.execute(
            """
            INSERT INTO study_schedules (student_id, subject_name, total_study_blocks, is_active, reschedule_summary, last_rescheduled_at)
            VALUES (?, ?, ?, 1, ?, ?)
            """,
            (student_id, subj, total_blocks, resched_summary, last_resched)
        )
        schedule_id = cur.lastrowid

        # Insert blocks
        for day in daily_blocks:
            d_date = day.get("date", "")
            d_type = day.get("day_type", "study")
            blocks = day.get("blocks", [])

            for order_idx, b in enumerate(blocks):
                cur.execute(
                    """
                    INSERT INTO schedule_blocks (
                        schedule_id, date_str, day_type, topic_id_str, topic_title, subtopic_title,
                        duration_minutes, start_time, end_time, block_type, completed, completed_at,
                        reschedule_reason, original_date, gcal_event_id, order_in_day
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        schedule_id,
                        d_date,
                        d_type,
                        b.get("topic_id", "t_unknown"),
                        b.get("topic_title", "Study Session"),
                        b.get("subtopic_title", ""),
                        int(b.get("duration_minutes", 60)),
                        b.get("start_time", "09:00"),
                        b.get("end_time", "10:00"),
                        b.get("block_type", "normal"),
                        1 if b.get("completed") else 0,
                        b.get("completed_at"),
                        b.get("reschedule_reason", ""),
                        b.get("original_date"),
                        b.get("gcal_event_id"),
                        order_idx
                    )
                )

        return schedule_id

    if conn is not None:
        return _op(conn)
    with get_db_connection() as c:
        return _op(c)


def load_active_schedule(
    student_id: int = 1,
    conn: Optional[sqlite3.Connection] = None
) -> Optional[Dict[str, Any]]:
    """
    Load active study schedule from SQLite into dictionary matching session_state['schedule'].
    """
    def _op(c: sqlite3.Connection):
        cur = c.cursor()
        cur.execute(
            """
            SELECT * FROM study_schedules
            WHERE student_id = ? AND is_active = 1
            ORDER BY id DESC LIMIT 1
            """,
            (student_id,)
        )
        sched_row = cur.fetchone()
        if not sched_row:
            return None

        schedule_id = sched_row["id"]
        cur.execute(
            """
            SELECT * FROM schedule_blocks
            WHERE schedule_id = ?
            ORDER BY date_str ASC, order_in_day ASC
            """,
            (schedule_id,)
        )
        block_rows = cur.fetchall()

        # Group blocks by date
        days_map: Dict[str, Dict[str, Any]] = {}
        for row in block_rows:
            date_str = row["date_str"]
            if date_str not in days_map:
                days_map[date_str] = {
                    "date": date_str,
                    "day_type": row["day_type"],
                    "blocks": []
                }
            
            days_map[date_str]["blocks"].append({
                "id": row["id"],
                "topic_id": row["topic_id_str"],
                "topic_title": row["topic_title"],
                "subtopic_title": row["subtopic_title"] or "",
                "duration_minutes": row["duration_minutes"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "block_type": row["block_type"],
                "completed": bool(row["completed"]),
                "completed_at": row["completed_at"],
                "reschedule_reason": row["reschedule_reason"] or "",
                "original_date": row["original_date"],
                "gcal_event_id": row["gcal_event_id"]
            })

        daily_blocks = list(days_map.values())
        return {
            "subject": sched_row["subject_name"],
            "daily_blocks": daily_blocks,
            "total_study_blocks": sched_row["total_study_blocks"] or sum(len(d["blocks"]) for d in daily_blocks),
            "reschedule_summary": json.loads(sched_row["reschedule_summary"] or "{}"),
            "last_rescheduled_at": sched_row["last_rescheduled_at"]
        }

    if conn is not None:
        return _op(conn)
    with get_db_connection() as c:
        return _op(c)


# ── Quizzes, Mock Exams & Weak Topics ────────────────────────────────────────

def record_quiz_result(
    quiz_data: Dict[str, Any],
    student_id: int = 1,
    conn: Optional[sqlite3.Connection] = None
) -> int:
    """
    Record a completed quiz in quizzes table, update topic_performances,
    and update weak_topics if score < 70%.
    """
    def _op(c: sqlite3.Connection) -> int:
        cur = c.cursor()
        t_id = quiz_data.get("topic_id", "unknown")
        t_title = quiz_data.get("topic_title", "General Quiz")
        score = float(quiz_data.get("score_pct", 0.0))
        correct = int(quiz_data.get("correct", 0))
        total = int(quiz_data.get("total", 0))
        questions = json.dumps(quiz_data.get("questions", []))
        answers = json.dumps(quiz_data.get("answers", []))

        cur.execute(
            """
            INSERT INTO quizzes (student_id, topic_id_str, topic_title, score_pct, correct_answers, total_questions, questions_data, student_answers)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (student_id, t_id, t_title, score, correct, total, questions, answers)
        )
        quiz_id = cur.lastrowid

        # Determine verdict
        if score < 50:
            verdict = "critical"
            urgency = "critical"
        elif score < 70:
            verdict = "weak"
            urgency = "high"
        elif score < 85:
            verdict = "satisfactory"
            urgency = "medium"
        else:
            verdict = "mastered"
            urgency = "resolved"

        # Record topic performance
        cur.execute(
            """
            INSERT INTO topic_performances (student_id, source_type, source_id, topic_id_str, topic_title, score_pct, verdict, priority_action)
            VALUES (?, 'quiz', ?, ?, ?, ?, ?, ?)
            """,
            (student_id, quiz_id, t_id, t_title, score, verdict, f"Quiz attempt ({score:.1f}%)")
        )

        # Update or resolve weak topic
        if score < 70.0:
            cur.execute(
                """
                INSERT INTO weak_topics (student_id, topic_id_str, topic_title, score_pct, urgency, recommended_action, status, identified_at)
                VALUES (?, ?, ?, ?, ?, ?, 'active', datetime('now', 'localtime'))
                ON CONFLICT(student_id, topic_id_str) DO UPDATE SET
                    score_pct = excluded.score_pct,
                    urgency = excluded.urgency,
                    status = 'active',
                    recommended_action = excluded.recommended_action
                """,
                (student_id, t_id, t_title, score, urgency, f"Revision recommended: scored {score:.1f}%")
            )
        else:
            # Mark as resolved if student cleared the weak threshold
            cur.execute(
                """
                UPDATE weak_topics
                SET status = 'resolved', score_pct = ?, resolved_at = datetime('now', 'localtime')
                WHERE student_id = ? AND topic_id_str = ?
                """,
                (score, student_id, t_id)
            )

        # Log activity
        cur.execute(
            """
            INSERT INTO student_activities (student_id, activity_type, title, details)
            VALUES (?, 'quiz_taken', ?, ?)
            """,
            (student_id, f"Quiz: {t_title}", json.dumps({"score_pct": score, "correct": correct, "total": total}))
        )

        return quiz_id

    if conn is not None:
        return _op(conn)
    with get_db_connection() as c:
        return _op(c)


def load_quiz_results(
    student_id: int = 1,
    conn: Optional[sqlite3.Connection] = None
) -> List[Dict[str, Any]]:
    """Load all recorded quizzes for a student."""
    def _op(c: sqlite3.Connection):
        cur = c.cursor()
        cur.execute(
            """
            SELECT * FROM quizzes
            WHERE student_id = ?
            ORDER BY id ASC
            """,
            (student_id,)
        )
        rows = cur.fetchall()
        results = []
        for r in rows:
            results.append({
                "id": r["id"],
                "topic_id": r["topic_id_str"],
                "topic_title": r["topic_title"],
                "score_pct": float(r["score_pct"]),
                "correct": r["correct_answers"],
                "total": r["total_questions"],
                "questions": json.loads(r["questions_data"] or "[]"),
                "answers": json.loads(r["student_answers"] or "[]"),
                "taken_at": r["taken_at"]
            })
        return results

    if conn is not None:
        return _op(conn)
    with get_db_connection() as c:
        return _op(c)


def record_mock_evaluation(
    mock_eval: Dict[str, Any],
    student_id: int = 1,
    conn: Optional[sqlite3.Connection] = None
) -> int:
    """
    Record mock exam evaluation in mock_exams, topic_performances, and weak_topics.
    """
    def _op(c: sqlite3.Connection) -> int:
        cur = c.cursor()
        topic_perf = mock_eval.get("topic_performance", [])
        total_q = sum(p.get("total", 0) for p in topic_perf) if topic_perf else 10
        avg_score = sum(p.get("score_pct", 0.0) for p in topic_perf) / max(1, len(topic_perf)) if topic_perf else 0.0

        cur.execute(
            """
            INSERT INTO mock_exams (student_id, exam_title, total_questions, total_score_pct, evaluation_summary)
            VALUES (?, 'Full Mock Exam', ?, ?, ?)
            """,
            (student_id, total_q, avg_score, json.dumps(mock_eval))
        )
        mock_id = cur.lastrowid

        for p in topic_perf:
            t_id = p.get("topic_id", "unknown")
            t_title = p.get("topic_title") or t_id
            score = float(p.get("score_pct", 0.0))
            verdict = p.get("verdict", "weak" if score < 70 else "satisfactory")
            action = p.get("priority_action", "")

            cur.execute(
                """
                INSERT INTO topic_performances (student_id, source_type, source_id, topic_id_str, topic_title, score_pct, verdict, priority_action)
                VALUES (?, 'mock_exam', ?, ?, ?, ?, ?, ?)
                """,
                (student_id, mock_id, t_id, t_title, score, verdict, action)
            )

            # Weak topic sync
            if score < 70.0 or verdict in ("critical", "weak"):
                urgency = "critical" if (score < 50 or verdict == "critical") else "high"
                cur.execute(
                    """
                    INSERT INTO weak_topics (student_id, topic_id_str, topic_title, score_pct, urgency, recommended_action, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'active')
                    ON CONFLICT(student_id, topic_id_str) DO UPDATE SET
                        score_pct = excluded.score_pct,
                        urgency = excluded.urgency,
                        recommended_action = excluded.recommended_action,
                        status = 'active'
                    """,
                    (student_id, t_id, t_title, score, urgency, action)
                )

        # Log activity
        cur.execute(
            """
            INSERT INTO student_activities (student_id, activity_type, title, details)
            VALUES (?, 'mock_exam_taken', 'Mock Exam Completed', ?)
            """,
            (student_id, json.dumps({"average_score_pct": avg_score, "topics_evaluated": len(topic_perf)}))
        )

        return mock_id

    if conn is not None:
        return _op(conn)
    with get_db_connection() as c:
        return _op(c)


def load_mock_evaluation(
    student_id: int = 1,
    conn: Optional[sqlite3.Connection] = None
) -> Optional[Dict[str, Any]]:
    """Load latest mock exam evaluation matching session_state['mock_evaluation']."""
    def _op(c: sqlite3.Connection):
        cur = c.cursor()
        cur.execute(
            """
            SELECT * FROM mock_exams
            WHERE student_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (student_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        return json.loads(row["evaluation_summary"] or "{}")

    if conn is not None:
        return _op(conn)
    with get_db_connection() as c:
        return _op(c)


def get_weak_topics(
    student_id: int = 1,
    status: str = "active",
    conn: Optional[sqlite3.Connection] = None
) -> List[Dict[str, Any]]:
    """Retrieve weak topics for student."""
    def _op(c: sqlite3.Connection):
        cur = c.cursor()
        if status:
            cur.execute(
                """
                SELECT * FROM weak_topics
                WHERE student_id = ? AND status = ?
                ORDER BY score_pct ASC
                """,
                (student_id, status)
            )
        else:
            cur.execute(
                """
                SELECT * FROM weak_topics
                WHERE student_id = ?
                ORDER BY score_pct ASC
                """,
                (student_id,)
            )
        rows = cur.fetchall()
        return [
            {
                "topic_id": r["topic_id_str"],
                "topic_title": r["topic_title"],
                "score_pct": float(r["score_pct"]),
                "urgency": r["urgency"],
                "recommended_action": r["recommended_action"],
                "status": r["status"],
                "identified_at": r["identified_at"]
            }
            for r in rows
        ]

    if conn is not None:
        return _op(conn)
    with get_db_connection() as c:
        return _op(c)


# ── Calendar Events & Spaced Revision ────────────────────────────────────────

def save_calendar_event(
    gcal_event_id: str,
    event_title: str,
    start_time_iso: str,
    end_time_iso: str,
    schedule_block_id: Optional[int] = None,
    student_id: int = 1,
    conn: Optional[sqlite3.Connection] = None
) -> int:
    """Save or update Google Calendar event sync record."""
    def _op(c: sqlite3.Connection) -> int:
        cur = c.cursor()
        cur.execute(
            """
            INSERT INTO calendar_events (student_id, schedule_block_id, gcal_event_id, event_title, start_time_iso, end_time_iso, sync_status, last_synced_at)
            VALUES (?, ?, ?, ?, ?, ?, 'synced', datetime('now', 'localtime'))
            ON CONFLICT(student_id, gcal_event_id) DO UPDATE SET
                event_title = excluded.event_title,
                start_time_iso = excluded.start_time_iso,
                end_time_iso = excluded.end_time_iso,
                sync_status = 'synced',
                last_synced_at = datetime('now', 'localtime')
            """,
            (student_id, schedule_block_id, gcal_event_id, event_title, start_time_iso, end_time_iso)
        )
        return cur.lastrowid

    if conn is not None:
        return _op(conn)
    with get_db_connection() as c:
        return _op(c)


def load_calendar_events(
    student_id: int = 1,
    conn: Optional[sqlite3.Connection] = None
) -> List[Dict[str, Any]]:
    """Retrieve all synchronized calendar events."""
    def _op(c: sqlite3.Connection):
        cur = c.cursor()
        cur.execute("SELECT * FROM calendar_events WHERE student_id = ? ORDER BY start_time_iso ASC", (student_id,))
        rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "gcal_event_id": r["gcal_event_id"],
                "event_title": r["event_title"],
                "start_time_iso": r["start_time_iso"],
                "end_time_iso": r["end_time_iso"],
                "sync_status": r["sync_status"],
                "last_synced_at": r["last_synced_at"]
            }
            for r in rows
        ]

    if conn is not None:
        return _op(conn)
    with get_db_connection() as c:
        return _op(c)


# ── App State Key-Value & Activities ─────────────────────────────────────────

def set_app_state(key: str, value: Any, conn: Optional[sqlite3.Connection] = None) -> None:
    """Store arbitrary JSON serializable state or metadata."""
    def _op(c: sqlite3.Connection):
        cur = c.cursor()
        val_str = json.dumps(value) if not isinstance(value, str) else value
        cur.execute(
            """
            INSERT INTO app_state (key, value, updated_at)
            VALUES (?, ?, datetime('now', 'localtime'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = datetime('now', 'localtime')
            """,
            (key, val_str)
        )

    if conn is not None:
        _op(conn)
    else:
        with get_db_connection() as c:
            _op(c)


def get_app_state(key: str, default: Any = None, conn: Optional[sqlite3.Connection] = None) -> Any:
    """Retrieve arbitrary state or metadata by key."""
    def _op(c: sqlite3.Connection):
        cur = c.cursor()
        cur.execute("SELECT value FROM app_state WHERE key = ?", (key,))
        row = cur.fetchone()
        if not row:
            return default
        raw = row["value"]
        try:
            return json.loads(raw)
        except Exception:
            return raw

    if conn is not None:
        return _op(conn)
    with get_db_connection() as c:
        return _op(c)


def record_student_activity(
    activity_type: str,
    title: str,
    details: Any = None,
    student_id: int = 1,
    conn: Optional[sqlite3.Connection] = None
) -> int:
    """Log an activity event for the student."""
    def _op(c: sqlite3.Connection) -> int:
        cur = c.cursor()
        det_str = json.dumps(details) if isinstance(details, (dict, list)) else str(details or "")
        cur.execute(
            """
            INSERT INTO student_activities (student_id, activity_type, title, details)
            VALUES (?, ?, ?, ?)
            """,
            (student_id, activity_type, title, det_str)
        )
        return cur.lastrowid

    if conn is not None:
        return _op(conn)
    with get_db_connection() as c:
        return _op(c)


def load_recent_activities(
    student_id: int = 1,
    limit: int = 20,
    conn: Optional[sqlite3.Connection] = None
) -> List[Dict[str, Any]]:
    """Retrieve student activity history."""
    def _op(c: sqlite3.Connection):
        cur = c.cursor()
        cur.execute(
            """
            SELECT * FROM student_activities
            WHERE student_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (student_id, limit)
        )
        rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "activity_type": r["activity_type"],
                "title": r["title"],
                "details": r["details"],
                "timestamp": r["timestamp"]
            }
            for r in rows
        ]

    if conn is not None:
        return _op(conn)
    with get_db_connection() as c:
        return _op(c)


# ── Full Session State Sync (Bridge for Streamlit & Storage API) ─────────────

def save_full_session_state(session_state: Dict[str, Any]) -> bool:
    """
    Save complete Streamlit session state dictionary transactionally into SQLite.
    Maps all keys into normalized relational tables.
    """
    try:
        with get_db_connection() as conn:
            # 1. Student profile
            s_prof = session_state.get("student_profile", {})
            s_name = s_prof.get("student_name", "TestStudent")
            d_hours = float(s_prof.get("daily_hours", 4.0))
            b_days = s_prof.get("blocked_days", [])
            p_times = s_prof.get("preferred_times", ["09:00", "14:00"])
            student_id = get_or_create_student(s_name, d_hours, b_days, p_times, conn=conn)

            # 2. Syllabus topic tree
            topic_tree = session_state.get("topic_tree")
            if topic_tree and isinstance(topic_tree, dict):
                save_syllabus_tree(topic_tree, student_id=student_id, conn=conn)

            # 3. Schedule
            schedule = session_state.get("schedule")
            if schedule and isinstance(schedule, dict) and "daily_blocks" in schedule:
                save_study_schedule(schedule, student_id=student_id, conn=conn)

            # 4. Quizzes
            quiz_results = session_state.get("quiz_results")
            if quiz_results and isinstance(quiz_results, list):
                # Clean existing quizzes to prevent duplicates on multi-save
                conn.execute("DELETE FROM quizzes WHERE student_id = ?", (student_id,))
                conn.execute("DELETE FROM topic_performances WHERE student_id = ? AND source_type = 'quiz'", (student_id,))
                for q in quiz_results:
                    record_quiz_result(q, student_id=student_id, conn=conn)

            # 5. Mock evaluation
            mock_eval = session_state.get("mock_evaluation")
            if mock_eval and isinstance(mock_eval, dict):
                record_mock_evaluation(mock_eval, student_id=student_id, conn=conn)

            # 6. Flexible app state items (daily_briefing, flashcards, gcal_event_map, last_reschedule_result, etc.)
            for k in [
                "subject", "daily_briefing", "weak_analysis", "flashcards",
                "gcal_event_map", "completed_revisions", "revision_history",
                "last_reschedule_result", "mock_results"
            ]:
                if k in session_state and session_state[k] is not None:
                    set_app_state(k, session_state[k], conn=conn)

        return True
    except Exception as e:
        logger.error(f"Error saving full session state to SQLite: {e}", exc_info=True)
        return False


def load_full_session_state(student_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Load complete student state from SQLite and reconstruct the full dictionary
    expected by Streamlit session state and all core modules.
    """
    state: Dict[str, Any] = {}
    try:
        with get_db_connection() as conn:
            profile = get_student_profile(student_name=student_name, conn=conn)
            if not profile:
                return {}
            student_id = profile["id"]
            state["student_profile"] = {
                "student_name": profile["student_name"],
                "daily_hours": profile["daily_hours"],
                "blocked_days": profile["blocked_days"],
                "preferred_times": profile["preferred_times"]
            }

            # Syllabus
            topic_tree = load_syllabus_tree(student_id=student_id, conn=conn)
            if topic_tree:
                state["topic_tree"] = topic_tree
                state["subject"] = topic_tree.get("subject", "")

            # Schedule
            schedule = load_active_schedule(student_id=student_id, conn=conn)
            if schedule:
                state["schedule"] = schedule

            # Quizzes
            quizzes = load_quiz_results(student_id=student_id, conn=conn)
            if quizzes:
                state["quiz_results"] = quizzes

            # Mock evaluation
            mock_eval = load_mock_evaluation(student_id=student_id, conn=conn)
            if mock_eval:
                state["mock_evaluation"] = mock_eval

            # App state items
            for k in [
                "subject", "daily_briefing", "weak_analysis", "flashcards",
                "gcal_event_map", "completed_revisions", "revision_history",
                "last_reschedule_result", "mock_results"
            ]:
                val = get_app_state(k, conn=conn)
                if val is not None:
                    state[k] = val

        return state
    except Exception as e:
        logger.error(f"Error loading full session state from SQLite: {e}", exc_info=True)
        return {}


def clear_student_data(student_id: int = 1) -> bool:
    """Clear active student records from SQLite."""
    try:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM schedule_blocks WHERE schedule_id IN (SELECT id FROM study_schedules WHERE student_id = ?)", (student_id,))
            conn.execute("DELETE FROM study_schedules WHERE student_id = ?", (student_id,))
            conn.execute("DELETE FROM quizzes WHERE student_id = ?", (student_id,))
            conn.execute("DELETE FROM mock_exams WHERE student_id = ?", (student_id,))
            conn.execute("DELETE FROM topic_performances WHERE student_id = ?", (student_id,))
            conn.execute("DELETE FROM weak_topics WHERE student_id = ?", (student_id,))
            conn.execute("DELETE FROM calendar_events WHERE student_id = ?", (student_id,))
            conn.execute("DELETE FROM app_state")
        return True
    except Exception as e:
        logger.error(f"Error clearing student data: {e}")
        return False
