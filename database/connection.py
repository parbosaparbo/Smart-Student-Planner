"""
StudyMind AI — Database Connection Manager
Provides thread-safe SQLite connections with WAL mode, foreign key enforcement,
and automatic transaction management.
"""
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional, Union
import logging

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import DATABASE_PATH, DATA_DIR

logger = logging.getLogger(__name__)


def ensure_db_dir(path: Optional[Union[str, Path]] = None) -> Path:
    """Ensure parent directory for database exists."""
    target_path = Path(path) if path else DATABASE_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    return target_path


def get_raw_connection(db_path: Optional[Union[str, Path]] = None) -> sqlite3.Connection:
    """
    Create and configure a SQLite connection with WAL mode and foreign keys enabled.
    """
    path = ensure_db_dir(db_path)
    conn = sqlite3.connect(
        str(path),
        check_same_thread=False,
        timeout=30.0,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
    )
    conn.row_factory = sqlite3.Row
    # Configure pragmas for performance and data integrity
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


@contextmanager
def get_db_connection(db_path: Optional[Union[str, Path]] = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for database connections with automatic transaction management.
    Commits on successful block execution, rolls back on exception.
    """
    conn = get_raw_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database transaction error: {e}", exc_info=True)
        raise
    finally:
        conn.close()
