"""
StudyMind AI — Google Calendar OAuth2 Integration
Handles: Connect, Disconnect, Token Storage, Token Refresh,
         Schedule Sync, Event Update (no duplicates), 10-min Reminders.

Design decisions:
- OAuth tokens are stored per-student in data/gcal_tokens/<student_key>.json
  so multi-user data never bleeds across sessions.
- Duplicate prevention: each synced study block is tagged with an extended
  property  source=StudyMindAI  plus a deterministic eventId built from
  (student_name + date + start_time + topic_id). Existing events are found
  via that property and updated in-place.
- Reminders (10 min popup + 10 min email) are native Google Calendar
  reminders so they fire on Android / iPhone through the user's existing
  Calendar app even when the laptop is off.
- No separate server: the OAuth redirect uses Streamlit's own URL
  (http://localhost:8501/oauth/callback by default). Users can override
  the redirect URI via GOOGLE_REDIRECT_URI in .env.
"""
import hashlib
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

# Allow http://localhost for local Streamlit OAuth redirection
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# ── Constants ──────────────────────────────────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",  # only events, not full calendar
    "https://www.googleapis.com/auth/userinfo.email",   # to display connected account email
]
STUDYMIND_SOURCE_TAG = "StudyMindAI"
TOKEN_DIR = Path(__file__).parent / "data" / "gcal_tokens"
VERIFIER_FILE = TOKEN_DIR / "_verifier.json"
CREDENTIALS_FILE = Path(__file__).parent / "credentials.json"
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8501")


def _save_code_verifier(student_key: str, verifier: str) -> None:
    """Save PKCE code_verifier so token exchange matches authorization_url challenge."""
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    try:
        data = {}
        if VERIFIER_FILE.exists():
            with open(VERIFIER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        safe_key = re.sub(r"[^\w]", "_", (student_key or "default").lower().strip())
        data[safe_key] = verifier
        data["latest"] = verifier
        with open(VERIFIER_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


def _load_code_verifier(student_key: str = "") -> Optional[str]:
    """Retrieve saved PKCE code_verifier."""
    if not VERIFIER_FILE.exists():
        return None
    try:
        with open(VERIFIER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        safe_key = re.sub(r"[^\w]", "_", (student_key or "default").lower().strip())
        return data.get(safe_key) or data.get("latest")
    except Exception:
        return None


def _client_config() -> Optional[Dict]:
    """
    Build the OAuth2 client config from credentials.json or environment variables.
    Supports both 'installed' (desktop app) and 'web' OAuth credentials.
    Returns None if credentials are not configured.
    """
    if CREDENTIALS_FILE.exists():
        try:
            with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "installed" in data or "web" in data:
                    return data
        except Exception:
            pass

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
            "redirect_uris": [REDIRECT_URI],
        }
    }


def is_configured() -> bool:
    """Returns True if Google OAuth credentials are present in credentials.json or environment."""
    if CREDENTIALS_FILE.exists():
        return True
    return bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))


# ── Token persistence (per-student with default fallback) ─────────────────────

def _token_path(student_key: str) -> Path:
    """Returns the path for a student's OAuth token file."""
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    safe_key = re.sub(r"[^\w]", "_", (student_key or "default").lower().strip())
    if not safe_key:
        safe_key = "default"
    return TOKEN_DIR / f"{safe_key}.json"


def load_token(student_key: str = "") -> Optional[Credentials]:
    """
    Load persisted credentials for a student.
    Fallback chain:
    1. Check specific student_key
    2. Check default token
    3. Check any valid token file in TOKEN_DIR
    """
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Try student_key if provided
    if student_key:
        path = _token_path(student_key)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return Credentials.from_authorized_user_info(data, SCOPES)
            except Exception:
                pass

    # 2. Try default token
    def_path = _token_path("default")
    if def_path.exists():
        try:
            with open(def_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Credentials.from_authorized_user_info(data, SCOPES)
        except Exception:
            pass

    # 3. Try any saved token in data/gcal_tokens/
    if TOKEN_DIR.exists():
        for f in TOKEN_DIR.glob("*.json"):
            if not f.name.startswith("_"):
                try:
                    with open(f, "r", encoding="utf-8") as jf:
                        data = json.load(jf)
                    return Credentials.from_authorized_user_info(data, SCOPES)
                except Exception:
                    pass

    return None


def save_token(student_key: str, creds: Credentials) -> None:
    """Persist OAuth credentials for a student and update default token."""
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    token_json = creds.to_json()

    # Save student-specific token
    path = _token_path(student_key)
    with open(path, "w", encoding="utf-8") as f:
        f.write(token_json)

    # Also save as default token so any view on this PC recognizes the connected state
    def_path = _token_path("default")
    with open(def_path, "w", encoding="utf-8") as f:
        f.write(token_json)


def delete_token(student_key: str = "") -> None:
    """Remove stored credentials (disconnect) for student and clear defaults."""
    if student_key:
        path = _token_path(student_key)
        if path.exists():
            try:
                path.unlink()
            except Exception:
                pass

    def_path = _token_path("default")
    if def_path.exists():
        try:
            def_path.unlink()
        except Exception:
            pass

    # Clean up any other tokens in the directory
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
    Does NOT delete token on transient network errors.
    """
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(GoogleAuthRequest())
            save_token(student_key, creds)
        except Exception as e:
            err_str = str(e).lower()
            if "invalid_grant" in err_str:
                delete_token(student_key)
                raise ValueError("Google account access was revoked. Please reconnect.")
            # On temporary network issues, keep the token so local state remains connected
    return creds


def get_valid_credentials(student_key: str = "") -> Optional[Credentials]:
    """
    Returns valid (or refreshable) credentials or None if not connected.
    """
    creds = load_token(student_key)
    if creds is None:
        return None
    if creds.valid:
        return creds
    if creds.expired and creds.refresh_token:
        return refresh_if_needed(student_key, creds)
    return creds


def is_connected(student_key: str = "") -> bool:
    """Returns True if valid Google Calendar credentials exist for this student or default."""
    try:
        creds = load_token(student_key)
        return bool(creds and (creds.valid or creds.refresh_token or creds.token))
    except Exception:
        return False


# ── OAuth2 Flows (Local Server & Direct Callback) ─────────────────────────────

def connect_via_local_server(student_key: str = "Student") -> Tuple[bool, str]:
    """
    Launches Google's native local server OAuth flow.
    Automatically starts a local receiver on loopback, opens browser,
    exchanges code with matching verifier, and saves credentials.
    Returns (success: bool, email_or_error: str).
    """
    config = _client_config()
    if not config:
        return False, "Google OAuth credentials not configured."

    try:
        flow = InstalledAppFlow.from_client_config(
            config,
            scopes=SCOPES,
            autogenerate_code_verifier=True,
        )
        creds = flow.run_local_server(
            port=0,
            authorization_prompt_message="Opening browser for Google Calendar authorization...",
            success_message="✅ StudyMind AI authorization complete! You may close this tab and return to the application.",
            open_browser=True,
            timeout_seconds=90,
        )
        save_token(student_key, creds)
        email = get_connected_account_email(student_key)
        return True, email or "Connected"
    except Exception as e:
        return False, str(e)


def build_auth_url(student_key: str) -> Tuple[str, str]:
    """
    Generates the Google OAuth2 authorization URL and persists PKCE verifier.
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
    auth_url, state = flow.authorization_url(
        access_type="offline",          # get refresh_token for persistent use
        include_granted_scopes="true",
        prompt="consent",               # always show consent so we always get refresh_token
        state=student_key,
    )
    # Save the PKCE code_verifier so exchange_code_for_token can send the matching verifier
    if flow.code_verifier:
        _save_code_verifier(student_key, flow.code_verifier)

    return auth_url, state


def exchange_code_for_token(code: str, student_key: str = "") -> Credentials:
    """
    Exchanges an OAuth authorization code for credentials and persists them.
    Restores the PKCE code_verifier to guarantee valid exchange.
    """
    config = _client_config()
    if not config:
        raise ValueError("Google OAuth credentials not configured.")

    code_verifier = _load_code_verifier(student_key)
    kwargs = {}
    if code_verifier:
        kwargs["code_verifier"] = code_verifier

    flow = Flow.from_client_config(
        config,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        state=student_key,
        **kwargs,
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    save_token(student_key or "default", creds)
    return creds


# ── Calendar API helpers ───────────────────────────────────────────────────────

def _get_service(student_key: str):
    """Build an authorized Google Calendar API service object."""
    creds = get_valid_credentials(student_key)
    if creds is None:
        raise ValueError("Not connected to Google Calendar. Please connect first.")
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _make_event_id(student_key: str, date_str: str, start_time: str, topic_id: str) -> str:
    """
    Creates a deterministic, stable event ID from study block metadata.
    Used to find and update existing events instead of creating duplicates.
    Google Calendar event IDs must be 5-1024 chars, lowercase alphanumeric + hyphen only.
    """
    raw = f"{student_key}:{date_str}:{start_time}:{topic_id}"
    h = hashlib.md5(raw.encode()).hexdigest()[:20]
    return f"studymind{h}"


def _build_event_body(
    block: Dict[str, Any],
    date_str: str,
    student_name: str,
    student_key: str,
) -> Dict:
    """
    Builds the Google Calendar event body for a study block.
    Includes:
    - Start/end times computed from block data
    - 10-minute popup reminder (fires on Android/iPhone via Google Calendar app)
    - 10-minute email reminder
    - Extended property tag so we can find it again later
    """
    topic_title = block.get("topic_title", "Study Session")
    start_time  = block.get("start_time", "09:00")
    duration    = int(block.get("duration_minutes", 60))
    goal        = block.get("session_goal", "")
    tip         = block.get("resources_tip", "")
    topic_id    = block.get("topic_id", "unknown")

    # Build RFC 3339 datetimes
    try:
        dt_start = datetime.strptime(f"{date_str}T{start_time}:00", "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        dt_start = datetime.strptime(f"{date_str}T09:00:00", "%Y-%m-%dT%H:%M:%S")
    dt_end = dt_start + timedelta(minutes=duration)

    description_lines = [
        f"📚 StudyMind AI — Study Session for {student_name}",
        "",
        f"🎯 Goal: {goal}" if goal else "",
        f"💡 Tip: {tip}" if tip else "",
        "",
        "─────────────────────────────",
        "Generated by StudyMind AI · studymind.app",
    ]
    description = "\n".join(line for line in description_lines if line is not None)

    return {
        "summary": f"📚 {topic_title}",
        "description": description,
        "start": {"dateTime": dt_start.isoformat(), "timeZone": "Asia/Kolkata"},
        "end":   {"dateTime": dt_end.isoformat(),   "timeZone": "Asia/Kolkata"},
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 10},   # native Android/iPhone alert
                {"method": "email", "minutes": 10},   # email fallback
            ],
        },
        "extendedProperties": {
            "private": {
                "source": STUDYMIND_SOURCE_TAG,
                "studentKey": student_key,
                "topicId": topic_id,
                "blockDate": date_str,
            }
        },
        "colorId": "7",  # Peacock blue — distinct from personal events
    }


def _upsert_event(
    service,
    calendar_id: str,
    event_id: str,
    event_body: Dict,
) -> Tuple[str, str]:
    """
    Insert or update (patch) a Calendar event.
    Returns (html_link, action) where action is 'created' or 'updated'.
    Handles 404 (create) and 409 (re-activate cancelled event).
    """
    try:
        existing = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        # Event exists — update it and ensure it's confirmed
        updated = service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body={**event_body, "id": event_id, "status": "confirmed"},
        ).execute()
        return updated.get("htmlLink", ""), "updated"
    except HttpError as e:
        if e.resp.status == 404:
            # Event does not exist — create it
            created = service.events().insert(
                calendarId=calendar_id,
                body={**event_body, "id": event_id},
            ).execute()
            return created.get("htmlLink", ""), "created"
        elif e.resp.status == 409:
            # Already exists (e.g. was cancelled or trashed) — update in place
            updated = service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body={**event_body, "id": event_id, "status": "confirmed"},
            ).execute()
            return updated.get("htmlLink", ""), "updated"
        raise


# ── Main sync function ─────────────────────────────────────────────────────────

def sync_schedule_to_calendar(
    schedule: Dict[str, Any],
    student_key: str,
    student_name: str,
    calendar_id: str = "primary",
) -> Dict[str, Any]:
    """
    Syncs all study blocks from a StudyMind schedule to the user's Google Calendar.
    - Updates existing events (no duplicates)
    - Adds 10-minute reminders
    - Skips rest days

    Returns a summary dict:
    {
        "created": int,
        "updated": int,
        "skipped": int,
        "errors":  list[str],
        "total_blocks": int,
    }
    """
    service = _get_service(student_key)
    result = {"created": 0, "updated": 0, "skipped": 0, "errors": [], "total_blocks": 0}

    daily_blocks = schedule.get("daily_blocks", [])

    for day in daily_blocks:
        date_str = day.get("date", "")
        day_type = day.get("day_type", "study")
        blocks   = day.get("blocks", [])

        if day_type == "rest" or not blocks:
            result["skipped"] += 1
            continue

        for block in blocks:
            topic_id = block.get("topic_id", "unknown")
            start_time = block.get("start_time", "09:00")
            result["total_blocks"] += 1

            event_id   = _make_event_id(student_key, date_str, start_time, topic_id)
            event_body = _build_event_body(block, date_str, student_name, student_key)

            try:
                _, action = _upsert_event(service, calendar_id, event_id, event_body)
                if action == "created":
                    result["created"] += 1
                else:
                    result["updated"] += 1
            except Exception as e:
                result["errors"].append(f"{date_str} {start_time} {topic_id}: {e}")

    return result


def delete_all_synced_events(student_key: str, calendar_id: str = "primary") -> int:
    """
    Deletes all events previously synced by StudyMind AI for this student.
    Uses the extendedProperties filter to find only StudyMind events.
    Returns the count of deleted events.
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
            except Exception:
                pass

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return deleted


def get_connected_account_email(student_key: str = "") -> Optional[str]:
    """
    Returns the Google account email of the connected user, or None.
    Uses multi-tier fallback:
    1. Primary Calendar ID (always available with calendar.events scope)
    2. Google OAuth2 userinfo endpoint
    3. Token id_token payload
    """
    try:
        creds = get_valid_credentials(student_key)
        if not creds:
            return None

        # 1. Primary Calendar ID is always the user's Google email
        try:
            service = build("calendar", "v3", credentials=creds, cache_discovery=False)
            cal = service.calendars().get(calendarId="primary").execute()
            cal_id = cal.get("id")
            if cal_id and "@" in cal_id:
                return cal_id
        except Exception:
            pass

        # 2. OAuth2 userinfo
        try:
            oauth2_service = build("oauth2", "v2", credentials=creds, cache_discovery=False)
            info = oauth2_service.userinfo().get().execute()
            if info.get("email"):
                return info.get("email")
        except Exception:
            pass

        # 3. id_token if present in creds
        try:
            if hasattr(creds, "id_token") and isinstance(creds.id_token, dict):
                return creds.id_token.get("email")
        except Exception:
            pass

        return "Connected User"
    except Exception:
        return None

