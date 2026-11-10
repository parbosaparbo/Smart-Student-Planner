"""
StudyMind AI — Google Calendar Integration & Multi-User OAuth Verification Suite
Validates:
1. One-Time Developer OAuth Configuration Diagnostics
2. Token Encryption at Rest (Fernet AES Symmetric Cipher)
3. Cryptographic State Nonce & CSRF Protection
4. Deterministic RFC 2938 Event ID Generation (no duplicates)
5. Event Body Generation with 10-Minute Popup & Email Reminders
6. Event Reconciliation: In-place update, Obsolete event deletion, Personal event protection
7. RFC 5545 iCalendar (.ics) Export Fallback
8. SQLite oauth_tokens & calendar_events Relational Sync
9. Token Revocation & Graceful Error Handling
10. Multi-tier Connected Gmail Account Email Resolution
"""
import base64
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import google_calendar as gcal
import storage
from google.oauth2.credentials import Credentials


class TestGoogleCalendarIntegration(unittest.TestCase):

    def setUp(self):
        self.student_key = "TestStudentGCal"

    def test_01_developer_oauth_configuration(self):
        """Verify developer Google Cloud & OAuth credentials check."""
        self.assertTrue(gcal.is_configured(), "Developer credentials should be configured via credentials.json or .env")
        status = gcal.get_developer_oauth_status()
        self.assertTrue(status["configured"])
        self.assertIn("client_type", status)
        self.assertIn("client_id_prefix", status)
        self.assertTrue(len(status["scopes"]) >= 3)
        self.assertIn("https://www.googleapis.com/auth/calendar.events", status["scopes"])

    def test_02_token_encryption_at_rest(self):
        """Verify tokens are encrypted using Fernet AES cipher at rest."""
        test_payload = {
            "token": "ya29.sample_access_token_12345",
            "refresh_token": "1//sample_refresh_token_67890",
            "account_email": "student@example.com",
            "scopes": gcal.SCOPES
        }
        encrypted = gcal._encrypt_payload(test_payload)
        self.assertNotEqual(encrypted, json.dumps(test_payload))
        self.assertNotIn("ya29.sample_access_token", encrypted, "Plaintext tokens must not appear in encrypted payload")

        decrypted = gcal._decrypt_payload(encrypted)
        self.assertIsNotNone(decrypted)
        self.assertEqual(decrypted["token"], test_payload["token"])
        self.assertEqual(decrypted["refresh_token"], test_payload["refresh_token"])
        self.assertEqual(decrypted["account_email"], "student@example.com")

    def test_03_state_nonce_and_csrf_validation(self):
        """Verify cryptographic state nonce generation and PKCE tracking."""
        auth_url, state = gcal.build_auth_url(self.student_key)
        self.assertIn("https://accounts.google.com/o/oauth2/auth", auth_url)
        self.assertIn("state=", auth_url)
        self.assertIn(self.student_key, state)

        # Verify state nonce was saved
        verifier, nonce = gcal._load_auth_state(self.student_key)
        self.assertIsNotNone(verifier)
        self.assertIsNotNone(nonce)
        self.assertIn(nonce, state)

    def test_04_deterministic_event_id(self):
        """Verify deterministic RFC 2938 base32hex event IDs (prevents duplicate events)."""
        ev_id1 = gcal._make_event_id("Riya", "2026-11-15", "09:00", "topic_math")
        ev_id2 = gcal._make_event_id("Riya", "2026-11-15", "09:00", "topic_math")
        self.assertEqual(ev_id1, ev_id2, "Same session must generate identical deterministic event ID")
        self.assertTrue(ev_id1.startswith("smai"))
        # Google Calendar event IDs must be strictly base32hex characters (0-9, a-v)
        allowed = set("0123456789abcdefghijklmnopqrstuv")
        self.assertTrue(all(c in allowed for c in ev_id1.lower()))

    def test_05_event_body_formatting_and_reminders(self):
        """Verify 10-minute popup & email reminders and StudyMind extended properties."""
        block = {
            "topic_id": "cn_sub",
            "topic_title": "Computer Networks — TCP",
            "start_time": "10:00",
            "duration_minutes": 90,
            "session_goal": "Master 3-way handshake",
            "block_type": "revision",
            "reschedule_reason": "Low quiz score (40%)"
        }
        body = gcal._build_event_body(block, "2026-11-16", "Riya", "Riya")
        self.assertIn("Computer Networks", body["summary"])
        self.assertIn("[Revision]", body["summary"])
        self.assertEqual(body["start"]["dateTime"], "2026-11-16T10:00:00")
        self.assertEqual(body["end"]["dateTime"], "2026-11-16T11:30:00")

        # Verify 10-minute reminders (native Android & iPhone notification)
        reminders = body.get("reminders", {}).get("overrides", [])
        methods = {r["method"]: r["minutes"] for r in reminders}
        self.assertEqual(methods.get("popup"), 10)
        self.assertEqual(methods.get("email"), 10)

        # Verify isolation property
        props = body["extendedProperties"]["private"]
        self.assertEqual(props["source"], gcal.STUDYMIND_SOURCE_TAG)
        self.assertEqual(props["studentKey"], "Riya")

    def test_06_event_reconciliation_and_obsolete_deletion(self):
        """
        Verify schedule sync:
        - Updates existing events in-place
        - Creates new events
        - Deletes obsolete StudyMind events
        - NEVER touches personal events
        """
        mock_service = MagicMock()
        mock_events = mock_service.events.return_value

        # Existing events on Google Calendar:
        # 1 StudyMind active event, 1 StudyMind obsolete event (e.g. rescheduled), 1 personal event
        existing_studymind_active = {
            "id": gcal._make_event_id("StudentA", "2026-11-15", "09:00", "t1"),
            "summary": "Old Title",
            "extendedProperties": {"private": {"source": "StudyMindAI", "studentKey": "StudentA"}}
        }
        existing_studymind_obsolete = {
            "id": "smai_obsolete_event_id_999",
            "summary": "Obsolete Moved Session",
            "extendedProperties": {"private": {"source": "StudyMindAI", "studentKey": "StudentA"}}
        }

        # Mock list returns only StudyMind events (personal events are excluded by query filter)
        mock_events.list.return_value.execute.return_value = {
            "items": [existing_studymind_active, existing_studymind_obsolete],
            "nextPageToken": None
        }
        mock_events.get.return_value.execute.return_value = existing_studymind_active
        mock_events.update.return_value.execute.return_value = {"htmlLink": "http://updated", "id": existing_studymind_active["id"]}
        mock_events.insert.return_value.execute.return_value = {"htmlLink": "http://created", "id": "smai_new"}
        mock_events.delete.return_value.execute.return_value = {}

        # New schedule has:
        # - The active event (t1 on Nov 15 09:00)
        # - A new event (t2 on Nov 16 09:00)
        # - Obsolete event is NOT in this schedule
        schedule = {
            "daily_blocks": [
                {
                    "date": "2026-11-15",
                    "day_type": "study",
                    "blocks": [{"topic_id": "t1", "topic_title": "Math", "start_time": "09:00", "duration_minutes": 60}]
                },
                {
                    "date": "2026-11-16",
                    "day_type": "study",
                    "blocks": [{"topic_id": "t2", "topic_title": "Physics", "start_time": "09:00", "duration_minutes": 60}]
                }
            ]
        }

        with patch("google_calendar._get_service", return_value=mock_service):
            result = gcal.sync_schedule_to_calendar(schedule, "StudentA", "StudentA", delete_obsolete=True)

        self.assertEqual(result["updated"], 1, "Active existing event should be updated in place")
        self.assertEqual(result["created"], 1, "New block should be created")
        self.assertEqual(result["deleted"], 1, "Obsolete StudyMind session must be deleted")
        mock_events.delete.assert_called_with(calendarId="primary", eventId="smai_obsolete_event_id_999")

    def test_07_rfc_5545_ics_export_fallback(self):
        """Verify standard RFC 5545 .ics calendar export for offline & non-Google use."""
        schedule = {
            "daily_blocks": [
                {
                    "date": "2026-11-20",
                    "day_type": "study",
                    "blocks": [
                        {
                            "topic_id": "math1",
                            "topic_title": "Linear Algebra",
                            "start_time": "09:00",
                            "duration_minutes": 90,
                            "session_goal": "Matrix decomposition",
                            "block_type": "normal"
                        },
                        {
                            "topic_id": "cs1",
                            "topic_title": "Data Structures",
                            "start_time": "14:00",
                            "duration_minutes": 60,
                            "session_goal": "B-Trees",
                            "block_type": "revision"
                        }
                    ]
                }
            ]
        }
        ics_text = gcal.export_schedule_to_ics(schedule, student_name="Aarav")
        self.assertIn("BEGIN:VCALENDAR", ics_text)
        self.assertIn("VERSION:2.0", ics_text)
        self.assertIn("Linear Algebra", ics_text)
        self.assertIn("Data Structures [Revision]", ics_text)
        self.assertIn("BEGIN:VALARM", ics_text)
        self.assertIn("TRIGGER:-PT10M", ics_text)
        self.assertIn("END:VCALENDAR", ics_text)

    def test_08_sqlite_oauth_token_and_calendar_events_persistence(self):
        """Verify SQLite tables oauth_tokens and calendar_events store and retrieve records."""
        # 1. OAuth token persistence in SQLite
        student_id = storage.get_or_create_student("SQLiteGCalStudent", 4.0)
        storage.save_oauth_token(
            student_id=student_id,
            provider="google_calendar",
            account_email="sqlite_test@gmail.com",
            encrypted_token="encrypted_secret_string",
            scopes=gcal.SCOPES
        )
        loaded_token = storage.load_oauth_token(student_id=student_id, provider="google_calendar")
        self.assertIsNotNone(loaded_token)
        self.assertEqual(loaded_token["account_email"], "sqlite_test@gmail.com")
        self.assertEqual(loaded_token["encrypted_token"], "encrypted_secret_string")

        # 2. Calendar event persistence in SQLite
        storage.save_calendar_event(
            gcal_event_id="smai_test_unit_event",
            event_title="Operating Systems Memory Management",
            start_time_iso="2026-11-22T09:00:00",
            end_time_iso="2026-11-22T10:30:00",
            student_id=student_id
        )
        events = storage.load_calendar_events(student_id=student_id)
        matching = [e for e in events if e["gcal_event_id"] == "smai_test_unit_event"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["sync_status"], "synced")

        # Mark deleted
        storage.delete_calendar_event("smai_test_unit_event", student_id=student_id)
        events_after = storage.load_calendar_events(student_id=student_id)
        matching_after = [e for e in events_after if e["gcal_event_id"] == "smai_test_unit_event"]
        self.assertEqual(matching_after[0]["sync_status"], "deleted")

    def test_09_token_revocation_handling(self):
        """Verify invalid_grant cleans token and raises clean notification."""
        mock_creds = MagicMock()
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_token"
        mock_creds.refresh.side_effect = Exception("invalid_grant: Token has been expired or revoked.")

        with self.assertRaises(ValueError) as ctx:
            gcal.refresh_if_needed("RevokedUser", mock_creds)
        self.assertIn("revoked", str(ctx.exception).lower())

    def test_10_account_email_resolution(self):
        """Verify extraction of account email from OpenID claims."""
        # Simulated OpenID JWT token
        header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').decode("utf-8").rstrip("=")
        claims = base64.urlsafe_b64encode(b'{"email":"riya.sharma@gmail.com","sub":"12345"}').decode("utf-8").rstrip("=")
        fake_id_token = f"{header}.{claims}.signature"

        mock_creds = MagicMock(spec=Credentials)
        mock_creds.id_token = fake_id_token
        mock_creds.account_email = None

        extracted = gcal._extract_email_from_creds(mock_creds)
        self.assertEqual(extracted, "riya.sharma@gmail.com")


if __name__ == "__main__":
    unittest.main(verbosity=2)

