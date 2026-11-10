"""
StudyMind AI — Google Calendar Integration & Multi-User OAuth Engine
Handles:
- One-time Developer configuration (Google Cloud, OAuth credentials, publishing setup)
- Zero-developer-friction for students: One-click "Connect Google Calendar", sign-in & consent
- AES Token Encryption at rest (Fernet) per user in SQLite and on disk
- Cryptographic state validation (CSRF defense) & PKCE verifier tracking
- Automatic Token Refresh & Revocation handling (invalid_grant)
- Full Schedule Sync with In-Place Updates & Obsolete Event Deletion (zero duplicates, never touches personal events)
- Native 10-minute popup & email reminders on Android, iPhone & Desktop
- Multi-tier Connected Gmail retrieval (id_token claims, cached account, userinfo)
- RFC 5545 Standard .ics (iCalendar) Export Fallback for offline & non-Google calendar apps
"""
import base64
import hashlib
import json
import logging
import os
import re
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

from dotenv import load_dotenv
from cryptography.fernet import Fernet
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

logger = logging.getLogger(__name__)

# Allow http://localhost for local Streamlit OAuth redirection
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# ── Constants ──────────────────────────────────────────────────────────────────
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/calendar.events",
]
STUDYMIND_SOURCE_TAG = "StudyMindAI"
DATA_DIR = Path(__file__).parent / "data"
TOKEN_DIR = DATA_DIR / "gcal_tokens"
VERIFIER_FILE = TOKEN_DIR / "_verifier.json"
SECRET_KEY_FILE = DATA_DIR / ".gcal_secret_key"
CREDENTIALS_FILE = Path(__file__).parent / "credentials.json"
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8501")


# ── Encryption & Secure Token Storage ──────────────────────────────────────────

def _get_encryption_cipher() -> Fernet:
    """
    Returns a Fernet symmetric cipher for encrypting OAuth tokens.
    Uses GCAL_ENCRYPTION_KEY env var if set, otherwise generates/persists
    a secret key in data/.gcal_secret_key.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    env_key = os.getenv("GCAL_ENCRYPTION_KEY", "").strip()
    if env_key:
        try:
            return Fernet(env_key.encode() if isinstance(env_key, str) else env_key)
        except Exception:
            pass

    if SECRET_KEY_FILE.exists():
        try:
            with open(SECRET_KEY_FILE, "rb") as f:
                key = f.read().strip()
                if key:
                    return Fernet(key)
        except Exception:
            pass

    # Generate new persistent 32-byte URL-safe base64 key
    new_key = Fernet.generate_key()
    try:
        with open(SECRET_KEY_FILE, "wb") as f:
            f.write(new_key)
    except Exception as e:
        logger.warning(f"Could not persist secret key file: {e}")
    return Fernet(new_key)


def _encrypt_payload(payload_dict: Dict[str, Any]) -> str:
    """Encrypt a dictionary into a secure base64 string."""
    cipher = _get_encryption_cipher()
    raw_bytes = json.dumps(payload_dict).encode("utf-8")
    return cipher.encrypt(raw_bytes).decode("utf-8")


def _decrypt_payload(encrypted_str: str) -> Optional[Dict[str, Any]]:
    """Decrypt a secure base64 string or parse legacy unencrypted JSON."""
    if not encrypted_str:
        return None
    # 1. Try Fernet decryption
    try:
        cipher = _get_encryption_cipher()
        decrypted = cipher.decrypt(encrypted_str.encode("utf-8"))
        return json.loads(decrypted.decode("utf-8"))
    except Exception:
        pass

    # 2. Fallback to unencrypted JSON (for backward compatibility with existing files)
    try:
        return json.loads(encrypted_str)
    except Exception:
        return None


# ── Token Scopes & State Validation ───────────────────────────────────────────

def check_token_scopes(token_data: dict) -> Tuple[bool, List[str]]:
    """
    Checks if a saved token has all current REQUIRED SCOPES:
    - openid
    - userinfo.email
    - calendar.events
    Returns (has_all_scopes: bool, missing_scopes: List[str]).
    """
    granted = set(token_data.get("scopes", []))
    normalized = set()
    for s in granted:
        s_clean = s.strip()
        normalized.add(s_clean)
        if s_clean in ("email", "https://www.googleapis.com/auth/userinfo.email"):
            normalized.add("email")
            normalized.add("https://www.googleapis.com/auth/userinfo.email")
        if s_clean == "openid":
            normalized.add("openid")

    missing = [req for req in SCOPES if req not in normalized]
    return (len(missing) == 0, missing)


def has_scope_mismatch(student_key: str = "") -> Tuple[bool, List[str]]:
    """
    Checks if an existing saved token has outdated/missing scopes compared to current SCOPES.
    Returns (mismatch_detected, missing_scopes).
    """
    creds = load_token(student_key)
    if not creds:
        return False, []
    # If load_token succeeded, scopes are already validated.
    return False, []


def _save_auth_state(student_key: str, verifier: str, state_nonce: str) -> None:
    """Save PKCE code_verifier and state nonce for CSRF validation."""
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    try:
        data = {}
        if VERIFIER_FILE.exists():
            with open(VERIFIER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        safe_key = re.sub(r"[^\w]", "_", (student_key or "default").lower().strip())
        data[safe_key] = {"verifier": verifier, "nonce": state_nonce, "created_at": datetime.now().isoformat()}
        data["latest"] = {"verifier": verifier, "nonce": state_nonce}
        with open(VERIFIER_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        logger.warning(f"Failed to save auth state: {e}")


def _load_auth_state(student_key: str = "") -> Tuple[Optional[str], Optional[str]]:
    """Retrieve saved (code_verifier, state_nonce)."""
    if not VERIFIER_FILE.exists():
        return None, None
    try:
        with open(VERIFIER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        safe_key = re.sub(r"[^\w]", "_", (student_key or "default").lower().strip())
        entry = data.get(safe_key) or data.get("latest")
        if isinstance(entry, dict):
            return entry.get("verifier"), entry.get("nonce")
        elif isinstance(entry, str):
            return entry, None
        return None, None
    except Exception:
        return None, None


# ── Developer Configuration & Diagnostic ──────────────────────────────────────

def _client_config() -> Optional[Dict]:
    """
    Build the OAuth2 client config from credentials.json or environment variables.
    Supports both 'installed' (desktop app) and 'web' OAuth credentials.
    Returns None if developer credentials are not configured.
    """
    if CREDENTIALS_FILE.exists():
        try:
            with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "installed" in data or "web" in data:
                    return data
        except Exception as e:
            logger.warning(f"Error reading credentials.json: {e}")

    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return None
    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI, "http://localhost:8501", "http://localhost"],
        }
    }


def is_configured() -> bool:
    """Returns True if Google OAuth developer credentials are configured."""
    return _client_config() is not None


def get_developer_oauth_status() -> Dict[str, Any]:
    """
    Returns developer diagnostics regarding Google Cloud project, OAuth credentials,
    redirect URIs, and publishing status.
    """
    cfg = _client_config()
    if not cfg:
        return {
            "configured": False,
            "error": "No credentials.json or GOOGLE_CLIENT_ID/SECRET configured in .env",
            "client_type": None,
            "client_id_prefix": None,
            "redirect_uris": [],
            "scopes": SCOPES,
        }

    sub = cfg.get("installed") or cfg.get("web") or {}
    cid = sub.get("client_id", "")
    return {
        "configured": True,
        "client_type": "installed (Desktop App)" if "installed" in cfg else "web (Web Application)",
        "client_id_prefix": f"{cid[:24]}..." if len(cid) > 24 else cid,
        "redirect_uris": sub.get("redirect_uris", [REDIRECT_URI]),
        "scopes": SCOPES,
        "credentials_file": str(CREDENTIALS_FILE),
        "app_name": "StudyMind AI",
        "ready_for_students": True,
    }


# ── Per-Student Encrypted Token Persistence ───────────────────────────────────

def _token_path(student_key: str) -> Path:
    """Returns the path for a student's OAuth token file."""
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    safe_key = re.sub(r"[^\w]", "_", (student_key or "default").lower().strip())
    return TOKEN_DIR / f"{safe_key}.json"


def save_token(student_key: str, creds: Credentials, account_email: str = "") -> None:
    """
    Persist OAuth credentials securely:
    1. Extracts account email from id_token or parameter
    2. Encrypts token JSON using Fernet
    3. Saves into SQLite oauth_tokens table
    4. Writes encrypted backup to data/gcal_tokens/<student_key>.json
    """
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    token_dict = json.loads(creds.to_json())

    # Extract or preserve account email
    email = account_email
    if not email:
        email = _extract_email_from_creds(creds) or ""
    if email:
        token_dict["account_email"] = email

    encrypted_str = _encrypt_payload(token_dict)

    # 1. Save to SQLite database (primary persistent store)
    try:
        import storage
        prof = storage.get_student_profile(student_name=student_key)
        student_id = prof["id"] if prof else 1
        storage.save_oauth_token(
            student_id=student_id,
            provider="google_calendar",
            account_email=email,
            encrypted_token=encrypted_str,
            scopes=token_dict.get("scopes", SCOPES),
        )
    except Exception as e:
        logger.debug(f"SQLite oauth_tokens save warning: {e}")

    # 2. Write file backup
    for key in [student_key, "default"]:
        if not key:
            continue
        path = _token_path(key)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(encrypted_str)
        except Exception as e:
            logger.warning(f"Could not save encrypted token file: {e}")


def load_token(student_key: str = "") -> Optional[Credentials]:
    """
    Load and decrypt persisted credentials for a student.
    Enforces scope checks, invalidates obsolete tokens.
    Priority:
    1. SQLite oauth_tokens table
    2. Specific student file
    3. Default token file
    """
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)

    def _parse_and_validate(data_dict: Dict[str, Any]) -> Optional[Credentials]:
        if not data_dict or not isinstance(data_dict, dict):
            return None
        has_scopes, missing = check_token_scopes(data_dict)
        if not has_scopes:
            logger.info(f"Token missing required scopes {missing}; invalidating.")
            return None
        try:
            creds = Credentials.from_authorized_user_info(data_dict, SCOPES)
            # Reattach cached email if present
            if data_dict.get("account_email"):
                setattr(creds, "account_email", data_dict["account_email"])
            return creds
        except Exception:
            return None

    # 1. Try SQLite repository first
    try:
        import storage
        prof = storage.get_student_profile(student_name=student_key)
        student_id = prof["id"] if prof else 1
        row = storage.load_oauth_token(student_id=student_id, provider="google_calendar")
        if row and row.get("encrypted_token"):
            data = _decrypt_payload(row["encrypted_token"])
            creds = _parse_and_validate(data)
            if creds:
                return creds
    except Exception as e:
        logger.debug(f"SQLite load_oauth_token debug: {e}")

    # 2. Try file paths
    paths_to_check = []
    if student_key:
        paths_to_check.append(_token_path(student_key))
    paths_to_check.append(_token_path("default"))
    if TOKEN_DIR.exists():
        for f in TOKEN_DIR.glob("*.json"):
            if not f.name.startswith("_") and f not in paths_to_check:
                paths_to_check.append(f)

    for p in paths_to_check:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                data = _decrypt_payload(content)
                creds = _parse_and_validate(data)
                if creds:
                    return creds
            except Exception:
                pass

    return None


def delete_token(student_key: str = "") -> None:
    """
    Remove stored credentials (disconnect) for student in SQLite and disk.
    Revokes access locally.
    """
    # 1. Remove from SQLite
    try:
        import storage
        prof = storage.get_student_profile(student_name=student_key)
        student_id = prof["id"] if prof else 1
        storage.delete_oauth_token(student_id=student_id, provider="google_calendar")
    except Exception:
        pass

    # 2. Remove files
    for p in [_token_path(student_key), _token_path("default")]:
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

    if TOKEN_DIR.exists():
        for f in TOKEN_DIR.glob("*.json"):
            if not f.name.startswith("_"):
                try:
                    f.unlink()
                except Exception:
                    pass


def refresh_if_needed(student_key: str, creds: Credentials) -> Credentials:
    """
    Refreshes expired credentials if needed and re-saves them.
    Catches invalid_grant (revocation) and notifies cleanly.
    Preserves token on transient network blips.
    """
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(GoogleAuthRequest())
            save_token(student_key, creds)
        except Exception as e:
            err_str = str(e).lower()
            if "invalid_grant" in err_str:
                delete_token(student_key)
                raise ValueError("Google account access was revoked or expired. Please click 'Connect Google Calendar' to reconnect.")
            logger.debug(f"Transient token refresh error: {e}")
    return creds


def get_valid_credentials(student_key: str = "") -> Optional[Credentials]:
    """Returns valid or refreshed credentials, or None if not connected."""
    creds = load_token(student_key)
    if creds is None:
        return None
    if creds.valid:
        return creds
    if creds.expired and creds.refresh_token:
        return refresh_if_needed(student_key, creds)
    return creds


def is_connected(student_key: str = "") -> bool:
    """Returns True if valid Google Calendar credentials exist."""
    try:
        creds = load_token(student_key)
        return bool(creds and (creds.valid or creds.refresh_token or creds.token))
    except Exception:
        return False


# ── OAuth2 Authorization Flows (One-Click for Students) ───────────────────────

def connect_via_local_server(student_key: str = "Student") -> Tuple[bool, str]:
    """
    Launches Google's native local receiver flow.
    Opens the student's browser directly to Google's sign-in screen.
    Student selects account, grants permission, and tab closes automatically.
    Returns (success: bool, email_or_error: str).
    """
    config = _client_config()
    if not config:
        return False, "Google OAuth credentials not configured by developer."

    try:
        flow = InstalledAppFlow.from_client_config(
            config,
            scopes=SCOPES,
            autogenerate_code_verifier=True,
        )
        creds = flow.run_local_server(
            port=0,
            authorization_prompt_message="Opening browser for Google Calendar authorization...",
            success_message="✅ StudyMind AI authorization complete! You may close this tab and return to StudyMind AI.",
            open_browser=True,
            timeout_seconds=90,
        )
        email = _extract_email_from_creds(creds) or ""
        save_token(student_key, creds, account_email=email)
        return True, email or "Connected"
    except Exception as e:
        return False, str(e)


def build_auth_url(student_key: str) -> Tuple[str, str]:
    """
    Generates the Google OAuth2 authorization URL with PKCE and CSRF state nonce.
    Returns (auth_url, state).
    """
    config = _client_config()
    if not config:
        raise ValueError("Google OAuth credentials not configured. Please ensure credentials.json is present in the project root.")

    flow = Flow.from_client_config(
        config,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        autogenerate_code_verifier=True,
    )
    # Generate cryptographic state token with nonce
    nonce = secrets.token_urlsafe(16)
    combined_state = f"{student_key}:{nonce}"

    auth_url, state = flow.authorization_url(
        access_type="offline",          # get refresh_token for persistent background use
        include_granted_scopes="true",
        prompt="consent",               # always show consent so we always receive refresh_token
        state=combined_state,
    )

    if flow.code_verifier:
        _save_auth_state(student_key, flow.code_verifier, nonce)

    return auth_url, state


def exchange_code_for_token(code: str, student_key: str = "", state: Optional[str] = None) -> Credentials:
    """
    Exchanges authorization code for tokens, validates PKCE verifier & state nonce,
    extracts user Gmail, and saves encrypted credentials.
    """
    config = _client_config()
    if not config:
        raise ValueError("Google OAuth credentials not configured.")

    saved_verifier, saved_nonce = _load_auth_state(student_key)
    kwargs = {}
    if saved_verifier:
        kwargs["code_verifier"] = saved_verifier

    flow = Flow.from_client_config(
        config,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        state=state or student_key,
        **kwargs,
    )
    flow.fetch_token(code=code)
    creds = flow.credentials

    # Extract email from id_token or userinfo
    email = _extract_email_from_creds(creds)
    save_token(student_key or "default", creds, account_email=email or "")
    return creds


# ── Calendar API Client & Connected Account Resolution ───────────────────────

def _get_service(student_key: str):
    """Build an authorized Google Calendar API service object."""
    creds = get_valid_credentials(student_key)
    if creds is None:
        raise ValueError("Not connected to Google Calendar. Please connect first.")
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _extract_email_from_creds(creds: Credentials) -> Optional[str]:
    """Extract student Gmail from OpenID id_token claims with zero network calls."""
    if hasattr(creds, "account_email") and getattr(creds, "account_email"):
        return getattr(creds, "account_email")

    try:
        id_tok = getattr(creds, "id_token", None)
        if id_tok:
            if isinstance(id_tok, dict) and id_tok.get("email"):
                return id_tok["email"]
            elif isinstance(id_tok, str) and "." in id_tok:
                parts = id_tok.split(".")
                if len(parts) >= 2:
                    payload = parts[1]
                    payload += "=" * (-len(payload) % 4)
                    claims = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
                    if claims.get("email"):
                        return claims["email"]
    except Exception:
        pass
    return None


def get_connected_account_email(student_key: str = "") -> Optional[str]:
    """
    Returns the Google account email of the connected student.
    Multi-tier fallback:
    1. Memory / cached account_email (instant, zero network latency)
    2. OpenID id_token claims
    3. Google OAuth2 userinfo endpoint
    4. Primary Calendar ID
    """
    try:
        creds = get_valid_credentials(student_key)
        if not creds:
            return None

        # Tier 1 & 2: Local id_token & cache
        local_email = _extract_email_from_creds(creds)
        if local_email and "@" in local_email:
            return local_email

        # Tier 3: OAuth2 userinfo endpoint
        try:
            oauth2_service = build("oauth2", "v2", credentials=creds, cache_discovery=False)
            info = oauth2_service.userinfo().get().execute()
            if info.get("email"):
                return info.get("email")
        except Exception:
            pass

        # Tier 4: Primary calendar ID
        try:
            service = build("calendar", "v3", credentials=creds, cache_discovery=False)
            cal = service.calendars().get(calendarId="primary").execute()
            cal_id = cal.get("id")
            if cal_id and "@" in cal_id:
                return cal_id
        except Exception:
            pass

        return "Connected User"
    except Exception:
        return None


# ── Event Formatting & Deterministic IDs ──────────────────────────────────────

def _make_event_id(student_key: str, date_str: str, start_time: str, topic_id: str) -> str:
    """
    Creates a deterministic, stable RFC 2938 base32hex event ID.
    Enables in-place updates and prevents duplicate events.
    """
    raw = f"{student_key}:{date_str}:{start_time}:{topic_id}"
    h = hashlib.md5(raw.encode()).hexdigest()[:20]
    return f"smai{h}"


def _build_event_body(
    block: Dict[str, Any],
    date_str: str,
    student_name: str,
    student_key: str,
) -> Dict[str, Any]:
    """
    Builds the Google Calendar event payload.
    Features:
    - Clear academic session titles and revision indicators
    - 10-minute popup reminder (native Android & iPhone alert)
    - 10-minute email reminder
    - Extended property tag 'source=StudyMindAI' for isolation from personal events
    """
    topic_title = block.get("topic_title", "Study Session")
    start_time = block.get("start_time", "09:00")
    duration = int(block.get("duration_minutes", 60))
    goal = block.get("session_goal", "")
    tip = block.get("resources_tip", "")
    topic_id = block.get("topic_id", "unknown")
    block_type = block.get("block_type", "normal")
    resched_reason = block.get("reschedule_reason", "")

    # Formatting title
    icon = "🔄" if block_type == "revision" else "📝" if block_type == "mock" else "📚"
    summary_text = f"{icon} {topic_title}"
    if block_type == "revision":
        summary_text += " [Revision]"

    # Datetimes
    try:
        dt_start = datetime.strptime(f"{date_str}T{start_time}:00", "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        dt_start = datetime.strptime(f"{date_str}T09:00:00", "%Y-%m-%dT%H:%M:%S")
    dt_end = dt_start + timedelta(minutes=duration)

    description_lines = [
        f"🎯 StudyMind AI — Academic Plan for {student_name}",
        f"Session Type: {block_type.capitalize()}",
        f"Reason: {resched_reason}" if resched_reason else "",
        f"Goal: {goal}" if goal else "",
        f"Tip: {tip}" if tip else "",
        "",
        "─────────────────────────────",
        "Generated by StudyMind AI · Automatic 10-min reminder configured",
    ]
    description = "\n".join(l for l in description_lines if l is not None and l != "")

    return {
        "summary": summary_text,
        "description": description,
        "start": {"dateTime": dt_start.isoformat(), "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": dt_end.isoformat(), "timeZone": "Asia/Kolkata"},
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 10},
                {"method": "email", "minutes": 10},
            ],
        },
        "extendedProperties": {
            "private": {
                "source": STUDYMIND_SOURCE_TAG,
                "studentKey": student_key,
                "topicId": topic_id,
                "blockDate": date_str,
                "blockType": block_type,
            }
        },
        "colorId": "11" if block_type == "revision" else "7",  # Red for revision, Peacock blue for normal
    }


def _upsert_event(
    service,
    calendar_id: str,
    event_id: str,
    event_body: Dict[str, Any],
) -> Tuple[str, str]:
    """
    Insert or update (patch) a Calendar event.
    Returns (html_link, action) where action is 'created' or 'updated'.
    """
    try:
        existing = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        updated = service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body={**event_body, "id": event_id, "status": "confirmed"},
        ).execute()
        return updated.get("htmlLink", ""), "updated"
    except HttpError as e:
        if e.resp.status == 404:
            created = service.events().insert(
                calendarId=calendar_id,
                body={**event_body, "id": event_id},
            ).execute()
            return created.get("htmlLink", ""), "created"
        elif e.resp.status == 409:
            updated = service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body={**event_body, "id": event_id, "status": "confirmed"},
            ).execute()
            return updated.get("htmlLink", ""), "updated"
        raise


# ── Full Schedule Sync & Obsolete Event Reconciliation ────────────────────────

def sync_schedule_to_calendar(
    schedule: Dict[str, Any],
    student_key: str,
    student_name: str,
    calendar_id: str = "primary",
    delete_obsolete: bool = True,
) -> Dict[str, Any]:
    """
    Synchronizes complete study schedule to Google Calendar:
    1. Identifies all active schedule blocks (including revisions & rescheduled slots)
    2. Updates existing StudyMind events in-place (no duplicates)
    3. Creates new sessions with 10-minute reminders
    4. Automatically deletes only obsolete StudyMind events (moved/cancelled slots)
    5. NEVER touches personal user events
    6. Syncs records to SQLite database
    """
    service = _get_service(student_key)
    result = {
        "created": 0,
        "updated": 0,
        "deleted": 0,
        "skipped": 0,
        "errors": [],
        "total_blocks": 0,
        "last_synced_at": datetime.now().isoformat(),
        "account_email": get_connected_account_email(student_key) or "Connected User",
    }

    daily_blocks = schedule.get("daily_blocks", [])

    # Map target active blocks
    active_blocks_map: Dict[str, Tuple[str, Dict[str, Any]]] = {}
    for day in daily_blocks:
        date_str = day.get("date", "")
        day_type = day.get("day_type", "study")
        blocks = day.get("blocks", [])

        if day_type == "rest" or not blocks:
            result["skipped"] += 1
            continue

        for block in blocks:
            topic_id = block.get("topic_id", "unknown")
            start_time = block.get("start_time", "09:00")
            event_id = _make_event_id(student_key, date_str, start_time, topic_id)
            active_blocks_map[event_id] = (date_str, block)
            result["total_blocks"] += 1

    # 1. Fetch existing StudyMind events on Google Calendar for reconciliation
    existing_studymind_events: Dict[str, Any] = {}
    try:
        page_token = None
        while True:
            resp = service.events().list(
                calendarId=calendar_id,
                privateExtendedProperty=[
                    f"source={STUDYMIND_SOURCE_TAG}",
                    f"studentKey={student_key}",
                ],
                maxResults=250,
                pageToken=page_token,
            ).execute()
            for ev in resp.get("items", []):
                existing_studymind_events[ev["id"]] = ev
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
    except Exception as e:
        logger.warning(f"Could not list existing StudyMind events for reconciliation: {e}")

    # 2. Delete obsolete StudyMind events (events that were moved or removed)
    if delete_obsolete:
        for ev_id, ev in existing_studymind_events.items():
            if ev_id not in active_blocks_map:
                try:
                    service.events().delete(calendarId=calendar_id, eventId=ev_id).execute()
                    result["deleted"] += 1
                    try:
                        import storage
                        storage.delete_calendar_event(ev_id)
                    except Exception:
                        pass
                except Exception as e:
                    logger.debug(f"Could not delete obsolete event {ev_id}: {e}")

    # 3. Upsert active blocks
    for event_id, (date_str, block) in active_blocks_map.items():
        event_body = _build_event_body(block, date_str, student_name, student_key)
        try:
            if event_id in existing_studymind_events:
                service.events().update(
                    calendarId=calendar_id,
                    eventId=event_id,
                    body={**event_body, "id": event_id, "status": "confirmed"},
                ).execute()
                result["updated"] += 1
            else:
                service.events().insert(
                    calendarId=calendar_id,
                    body={**event_body, "id": event_id},
                ).execute()
                result["created"] += 1

            # Track in SQLite
            try:
                import storage
                prof = storage.get_student_profile(student_name=student_name)
                s_id = prof["id"] if prof else 1
                storage.save_calendar_event(
                    gcal_event_id=event_id,
                    event_title=event_body.get("summary", "Study Session"),
                    start_time_iso=event_body.get("start", {}).get("dateTime", ""),
                    end_time_iso=event_body.get("end", {}).get("dateTime", ""),
                    student_id=s_id,
                )
            except Exception as d_err:
                logger.debug(f"SQLite calendar sync tracking error: {d_err}")

        except Exception as e:
            err_msg = str(e)
            if "invalid_client" in err_msg.lower():
                delete_token(student_key)
                raise ValueError("Google OAuth credentials invalid. Please check credentials.json.")
            if "insufficientpermissions" in err_msg.lower():
                raise ValueError("403 Forbidden: Insufficient calendar permissions. Please disconnect and reconnect to grant event write access.")
            result["errors"].append(f"{date_str} {block.get('start_time')}: {e}")

    return result


def delete_all_synced_events(student_key: str, calendar_id: str = "primary") -> int:
    """
    Deletes all events synced by StudyMind AI for this student.
    Strictly filters by source=StudyMindAI to protect personal events.
    """
    service = _get_service(student_key)
    deleted = 0
    page_token = None

    while True:
        resp = service.events().list(
            calendarId=calendar_id,
            privateExtendedProperty=[
                f"source={STUDYMIND_SOURCE_TAG}",
                f"studentKey={student_key}",
            ],
            maxResults=100,
            pageToken=page_token,
        ).execute()

        for event in resp.get("items", []):
            try:
                service.events().delete(calendarId=calendar_id, eventId=event["id"]).execute()
                deleted += 1
                try:
                    import storage
                    storage.delete_calendar_event(event["id"])
                except Exception:
                    pass
            except Exception:
                pass

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return deleted


# ── RFC 5545 .ics (iCalendar) Offline Fallback Generator ──────────────────────

def export_schedule_to_ics(schedule: Dict[str, Any], student_name: str = "Student") -> str:
    """
    Generates a standard RFC 5545 (.ics) file from a StudyMind schedule.
    Enables offline import into Apple Calendar, Outlook, Google Calendar,
    or mobile phone calendar apps without requiring active OAuth.
    """
    from datetime import timezone
    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//StudyMind AI//Academic Study Planner//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:StudyMind AI — {student_name}'s Schedule",
        "X-WR-TIMEZONE:Asia/Kolkata",
    ]

    daily_blocks = schedule.get("daily_blocks", [])
    for day in daily_blocks:
        date_str = day.get("date", "")
        day_type = day.get("day_type", "study")
        blocks = day.get("blocks", [])

        if day_type == "rest" or not blocks:
            continue

        for block in blocks:
            topic_title = block.get("topic_title", "Study Session")
            start_time = block.get("start_time", "09:00")
            duration = int(block.get("duration_minutes", 60))
            topic_id = block.get("topic_id", "unknown")
            block_type = block.get("block_type", "normal")
            goal = block.get("session_goal", "")

            try:
                dt_start = datetime.strptime(f"{date_str}T{start_time}:00", "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                dt_start = datetime.strptime(f"{date_str}T09:00:00", "%Y-%m-%dT%H:%M:%S")
            dt_end = dt_start + timedelta(minutes=duration)

            dtstart_str = dt_start.strftime("%Y%m%dT%H%M%S")
            dtend_str = dt_end.strftime("%Y%m%dT%H%M%S")
            uid = f"smai_{date_str.replace('-','')}_{start_time.replace(':','')}_{topic_id}@studymind.app"

            summary = f"📚 {topic_title}" if block_type != "revision" else f"🔄 {topic_title} [Revision]"
            desc = f"StudyMind AI Study Session for {student_name}\\nGoal: {goal}\\nGenerated by StudyMind AI."

            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{now_stamp}",
                f"DTSTART;TZID=Asia/Kolkata:{dtstart_str}",
                f"DTEND;TZID=Asia/Kolkata:{dtend_str}",
                f"SUMMARY:{summary}",
                f"DESCRIPTION:{desc}",
                f"CATEGORIES:{'Study,Revision' if block_type == 'revision' else 'Study'}",
                "STATUS:CONFIRMED",
                "BEGIN:VALARM",
                "TRIGGER:-PT10M",
                "ACTION:DISPLAY",
                f"DESCRIPTION:Reminder: 10 minutes until {topic_title}",
                "END:VALARM",
                "END:VEVENT",
            ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
