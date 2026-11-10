"""
StudyMind AI — Database Schema
Defines normalized SQLite tables, foreign keys, indexes, and constraints.
Engineered for local single-student execution while being fully extensible
to multi-tenant / cloud database systems without structural changes.
"""
import sqlite3
import logging

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
-- 1. Students & Preferences
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_name TEXT NOT NULL UNIQUE,
    daily_hours REAL DEFAULT 4.0,
    blocked_days TEXT DEFAULT '[]',         -- JSON array, e.g. ["Sunday"]
    preferred_times TEXT DEFAULT '[]',      -- JSON array, e.g. ["09:00", "14:00"]
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 2. Subjects (Syllabus Root)
CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject_name TEXT NOT NULL,
    exam_type TEXT DEFAULT '',
    has_electives INTEGER DEFAULT 0,
    total_estimated_hours REAL DEFAULT 0.0,
    sha256 TEXT DEFAULT '',
    tier_used TEXT DEFAULT '',
    document_metrics TEXT DEFAULT '{}',    -- JSON metadata
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(student_id, subject_name)
);

-- 3. Topics
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    topic_code TEXT NOT NULL,              -- e.g. 't1', 'cn'
    title TEXT NOT NULL,
    difficulty INTEGER DEFAULT 3,
    priority INTEGER DEFAULT 3,
    estimated_hours REAL DEFAULT 0.0,
    is_elective INTEGER DEFAULT 0,
    elective_group TEXT DEFAULT NULL,
    prerequisites TEXT DEFAULT '[]',       -- JSON array
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(subject_id, topic_code)
);

-- 4. Subtopics
CREATE TABLE IF NOT EXISTS subtopics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    subtopic_code TEXT NOT NULL,           -- e.g. 't1_s1'
    title TEXT NOT NULL,
    estimated_hours REAL DEFAULT 0.0,
    key_concepts TEXT DEFAULT '[]',        -- JSON array
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(topic_id, subtopic_code)
);

-- 5. Quizzes & Exam History
CREATE TABLE IF NOT EXISTS quizzes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    topic_id_str TEXT NOT NULL,
    topic_title TEXT NOT NULL,
    score_pct REAL NOT NULL,
    correct_answers INTEGER NOT NULL,
    total_questions INTEGER NOT NULL,
    questions_data TEXT DEFAULT '[]',      -- JSON array of questions
    student_answers TEXT DEFAULT '[]',     -- JSON array of user responses
    taken_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 6. Mock Exams
CREATE TABLE IF NOT EXISTS mock_exams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    exam_title TEXT NOT NULL,
    total_questions INTEGER NOT NULL,
    total_score_pct REAL DEFAULT 0.0,
    questions_data TEXT DEFAULT '[]',      -- JSON array
    evaluation_summary TEXT DEFAULT '{}',  -- JSON evaluation details
    taken_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 7. Topic-wise Performance History
CREATE TABLE IF NOT EXISTS topic_performances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,             -- 'quiz' or 'mock_exam'
    source_id INTEGER,                     -- References quizzes.id or mock_exams.id
    topic_id_str TEXT NOT NULL,
    topic_title TEXT NOT NULL,
    score_pct REAL NOT NULL,
    verdict TEXT DEFAULT 'satisfactory',   -- 'critical', 'weak', 'satisfactory', 'mastered'
    priority_action TEXT DEFAULT '',
    recorded_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 8. Weak Topics
CREATE TABLE IF NOT EXISTS weak_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    topic_id_str TEXT NOT NULL,
    topic_title TEXT NOT NULL,
    score_pct REAL NOT NULL,
    urgency TEXT NOT NULL,                 -- 'critical', 'high', 'medium'
    recommended_action TEXT DEFAULT '',
    status TEXT DEFAULT 'active',          -- 'active', 'scheduled', 'resolved'
    identified_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    resolved_at TEXT DEFAULT NULL,
    UNIQUE(student_id, topic_id_str)
);

-- 9. Study Schedules
CREATE TABLE IF NOT EXISTS study_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject_name TEXT NOT NULL,
    total_study_blocks INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    reschedule_summary TEXT DEFAULT '{}',  -- JSON summary of rescheduling
    last_rescheduled_at TEXT DEFAULT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 10. Schedule Blocks (Individual daily study sessions)
CREATE TABLE IF NOT EXISTS schedule_blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER NOT NULL REFERENCES study_schedules(id) ON DELETE CASCADE,
    date_str TEXT NOT NULL,                -- 'YYYY-MM-DD'
    day_type TEXT DEFAULT 'study',         -- 'study', 'rest', 'revision', 'mock_exam'
    topic_id_str TEXT NOT NULL,
    topic_title TEXT NOT NULL,
    subtopic_title TEXT DEFAULT '',
    duration_minutes INTEGER DEFAULT 60,
    start_time TEXT DEFAULT '09:00',
    end_time TEXT DEFAULT '10:00',
    block_type TEXT DEFAULT 'normal',      -- 'normal', 'revision', 'mock'
    completed INTEGER DEFAULT 0,
    completed_at TEXT DEFAULT NULL,
    reschedule_reason TEXT DEFAULT '',
    original_date TEXT DEFAULT NULL,
    gcal_event_id TEXT DEFAULT NULL,
    order_in_day INTEGER DEFAULT 0
);

-- 11. Revision History & Spaced Repetition
CREATE TABLE IF NOT EXISTS revision_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    topic_id_str TEXT NOT NULL,
    topic_title TEXT NOT NULL,
    revision_interval INTEGER DEFAULT 1,   -- Days after initial learning (e.g. 1, 3, 7)
    scheduled_date TEXT NOT NULL,          -- 'YYYY-MM-DD'
    completed INTEGER DEFAULT 0,
    completed_at TEXT DEFAULT NULL,
    notes TEXT DEFAULT ''
);

-- 12. Google Calendar Event Mappings & Sync Status
CREATE TABLE IF NOT EXISTS calendar_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    schedule_block_id INTEGER REFERENCES schedule_blocks(id) ON DELETE SET NULL,
    gcal_event_id TEXT NOT NULL,
    calendar_id TEXT DEFAULT 'primary',
    event_title TEXT NOT NULL,
    start_time_iso TEXT NOT NULL,
    end_time_iso TEXT NOT NULL,
    sync_status TEXT DEFAULT 'synced',     -- 'synced', 'pending', 'error', 'deleted'
    last_synced_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    error_message TEXT DEFAULT NULL,
    UNIQUE(student_id, gcal_event_id)
);

-- 13. Student Progress & Activity History
CREATE TABLE IF NOT EXISTS student_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    activity_type TEXT NOT NULL,           -- 'quiz_taken', 'reschedule_triggered', 'study_completed', etc.
    title TEXT NOT NULL,
    details TEXT DEFAULT '{}',             -- JSON details or text
    timestamp TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 14. Database Backup Metadata
CREATE TABLE IF NOT EXISTS database_backups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backup_filename TEXT NOT NULL,
    backup_path TEXT NOT NULL,
    backup_type TEXT NOT NULL,             -- 'daily', 'pre_migration', 'manual'
    file_size_bytes INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'valid',  -- 'valid', 'corrupted'
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 15. User OAuth Tokens (Encrypted per-student token storage)
CREATE TABLE IF NOT EXISTS oauth_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    provider TEXT DEFAULT 'google_calendar',
    account_email TEXT DEFAULT '',
    encrypted_token TEXT NOT NULL,
    scopes TEXT DEFAULT '[]',              -- JSON array of granted scopes
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(student_id, provider)
);

-- 16. Flexible Application State & Key-Value Metadata
CREATE TABLE IF NOT EXISTS app_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,                   -- JSON or string
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ── Indexes for Fast Query Performance ───────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_topics_subject ON topics(subject_id);
CREATE INDEX IF NOT EXISTS idx_subtopics_topic ON subtopics(topic_id);
CREATE INDEX IF NOT EXISTS idx_quizzes_student ON quizzes(student_id, taken_at);
CREATE INDEX IF NOT EXISTS idx_topic_perf_student ON topic_performances(student_id, topic_id_str);
CREATE INDEX IF NOT EXISTS idx_weak_topics_student ON weak_topics(student_id, status);
CREATE INDEX IF NOT EXISTS idx_schedules_student ON study_schedules(student_id, is_active);
CREATE INDEX IF NOT EXISTS idx_blocks_schedule_date ON schedule_blocks(schedule_id, date_str);
CREATE INDEX IF NOT EXISTS idx_blocks_gcal ON schedule_blocks(gcal_event_id);
CREATE INDEX IF NOT EXISTS idx_cal_events_student ON calendar_events(student_id, gcal_event_id);
CREATE INDEX IF NOT EXISTS idx_oauth_tokens_student ON oauth_tokens(student_id, provider);
CREATE INDEX IF NOT EXISTS idx_activities_student ON student_activities(student_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_revision_student ON revision_history(student_id, scheduled_date);
"""


def init_database(conn: sqlite3.Connection) -> None:
    """Initialize all SQLite tables and indexes."""
    cursor = conn.cursor()
    cursor.executescript(SCHEMA_SQL)
    conn.commit()
    logger.info("StudyMind AI database schema initialized successfully.")

