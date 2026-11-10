"""
StudyMind AI — Database Backup & Recovery System
Supports:
- Daily automatic SQLite backups
- Pre-migration and schema-change backups
- Safe online backups via SQLite Backup API (conn.backup)
- Backup integrity validation via PRAGMA integrity_check
- Safe point-in-time database restoration with rollback safeguards
"""
import os
import shutil
import sqlite3
import sys
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import logging

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import DATABASE_PATH, BACKUP_DIR
from database.connection import get_raw_connection, ensure_db_dir

logger = logging.getLogger(__name__)


def ensure_backup_dir() -> Path:
    """Ensure the backup directory exists."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUP_DIR


def validate_backup(backup_path: Union[str, Path]) -> Tuple[bool, str]:
    """
    Validate backup database integrity using PRAGMA integrity_check.
    Returns (is_valid, message).
    """
    path = Path(backup_path)
    if not path.exists():
        return False, f"Backup file does not exist: {path}"
    if path.stat().st_size == 0:
        return False, "Backup file is empty (0 bytes)"

    try:
        conn = sqlite3.connect(str(path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()
        conn.close()
        if result and result[0] == "ok":
            return True, "Integrity check passed (ok)"
        return False, f"Integrity check failed: {result}"
    except Exception as e:
        return False, f"Integrity validation error: {e}"


def create_backup(
    db_path: Optional[Union[str, Path]] = None,
    backup_type: str = "daily",
    tag: str = ""
) -> Dict[str, Union[str, int, bool]]:
    """
    Create a safe online backup of the SQLite database using conn.backup().
    Saves to BACKUP_DIR with timestamp.
    Validates backup and records metadata in database_backups table.
    """
    source_path = Path(db_path) if db_path else DATABASE_PATH
    if not source_path.exists():
        logger.warning(f"Source database {source_path} does not exist; skipping backup.")
        return {
            "success": False,
            "error": "Source database file does not exist",
            "backup_path": ""
        }

    bdir = ensure_backup_dir()
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{tag}" if tag else ""
    filename = f"studymind_{backup_type}_{now_str}{suffix}.db"
    dest_path = bdir / filename

    try:
        source_conn = get_raw_connection(source_path)
        dest_conn = sqlite3.connect(str(dest_path))
        
        # SQLite online backup API
        source_conn.backup(dest_conn)
        dest_conn.close()

        # Validate the generated backup
        is_valid, val_msg = validate_backup(dest_path)
        file_size = dest_path.stat().st_size

        # Record backup in source database if valid
        if is_valid:
            try:
                source_conn.execute(
                    """
                    INSERT INTO database_backups (backup_filename, backup_path, backup_type, file_size_bytes, status, created_at)
                    VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime'))
                    """,
                    (filename, str(dest_path), backup_type, file_size, "valid")
                )
                source_conn.commit()
            except Exception as e:
                logger.warning(f"Could not record backup in database_backups table: {e}")

        source_conn.close()

        if not is_valid:
            logger.error(f"Backup validation failed: {val_msg}")
            return {
                "success": False,
                "error": f"Validation failed: {val_msg}",
                "backup_path": str(dest_path)
            }

        logger.info(f"Successfully created {backup_type} backup: {dest_path} ({file_size} bytes)")
        return {
            "success": True,
            "filename": filename,
            "backup_path": str(dest_path),
            "file_size_bytes": file_size,
            "backup_type": backup_type,
            "timestamp": now_str
        }
    except Exception as e:
        logger.error(f"Backup creation error: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "backup_path": ""
        }


def auto_daily_backup(db_path: Optional[Union[str, Path]] = None) -> Optional[Dict[str, Any]]:
    """
    Check if a daily backup was already created today. If not, trigger one.
    """
    bdir = ensure_backup_dir()
    today_str = date.today().strftime("%Y%m%d")
    existing_today = list(bdir.glob(f"studymind_daily_{today_str}_*.db"))
    if existing_today:
        return None  # Daily backup already taken today
    
    return create_backup(db_path, backup_type="daily")


def restore_backup(
    backup_path: Union[str, Path],
    target_db_path: Optional[Union[str, Path]] = None
) -> Dict[str, Union[bool, str]]:
    """
    Safely restore the active SQLite database from a validated backup.
    1. Validates the backup file first.
    2. Takes a safety snapshot of the target DB before overwriting.
    3. Replaces the target DB using file copy.
    4. Validates the restored target DB.
    """
    src = Path(backup_path)
    dest = Path(target_db_path) if target_db_path else DATABASE_PATH

    is_valid, msg = validate_backup(src)
    if not is_valid:
        return {"success": False, "error": f"Cannot restore invalid backup: {msg}"}

    # Create safety snapshot of active database if it exists
    safety_snapshot = None
    if dest.exists():
        safety_snapshot = dest.with_suffix(f".pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak")
        try:
            shutil.copy2(dest, safety_snapshot)
        except Exception as e:
            return {"success": False, "error": f"Failed to create pre-restore safety snapshot: {e}"}

    try:
        shutil.copy2(src, dest)
        # Validate restored file
        restored_valid, restored_msg = validate_backup(dest)
        if not restored_valid:
            # Rollback
            if safety_snapshot and safety_snapshot.exists():
                shutil.copy2(safety_snapshot, dest)
            return {"success": False, "error": f"Restored file failed integrity check: {restored_msg}. Rolled back."}
        
        logger.info(f"Database successfully restored from {src}")
        return {"success": True, "message": f"Successfully restored database from {src.name}"}
    except Exception as e:
        if safety_snapshot and safety_snapshot.exists():
            shutil.copy2(safety_snapshot, dest)
        return {"success": False, "error": f"Database restoration failed: {e}. Rolled back."}


def list_backups() -> List[Dict[str, Union[str, int]]]:
    """List all available backups sorted by modification time (newest first)."""
    bdir = ensure_backup_dir()
    backups = []
    for f in bdir.glob("studymind_*.db"):
        valid, msg = validate_backup(f)
        backups.append({
            "filename": f.name,
            "path": str(f),
            "size_bytes": f.stat().st_size,
            "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            "valid": valid
        })
    backups.sort(key=lambda x: x["modified"], reverse=True)
    return backups
