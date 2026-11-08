import google_calendar as gcal
from google.oauth2.credentials import Credentials
import json

print("=== TESTING GOOGLE OAUTH SCOPES & MIGRATION ===")

# 1. Verify SCOPES definition
expected_scopes = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/calendar.events"
]
print("1. Current SCOPES:", gcal.SCOPES)
for s in expected_scopes:
    assert s in gcal.SCOPES, f"Missing scope: {s}"
assert len(gcal.SCOPES) == 3, f"Expected exactly 3 scopes, got {len(gcal.SCOPES)}"
print("✅ SCOPES definition is consistent and complete!")

# 2. Test check_token_scopes function
old_data = {
    "token": "old_token_123",
    "refresh_token": "old_ref_123",
    "scopes": [
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/userinfo.email"
    ]
}
valid, missing = gcal.check_token_scopes(old_data)
print(f"2a. Old token validation: valid={valid}, missing={missing}")
assert valid == False, "Old token missing openid must be invalid!"
assert "openid" in missing, "Missing scopes must list openid!"

new_data = {
    "token": "new_token_456",
    "refresh_token": "new_ref_456",
    "scopes": [
        "openid",
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/userinfo.email"
    ]
}
valid_new, missing_new = gcal.check_token_scopes(new_data)
print(f"2b. New token validation: valid={valid_new}, missing={missing_new}")
assert valid_new == True, "New token with all scopes must be valid!"
assert len(missing_new) == 0

# 3. Test on-disk scope mismatch detection & auto-invalidation
old_creds = Credentials(
    token="tok_old",
    refresh_token="ref_old",
    token_uri="https://oauth2.googleapis.com/token",
    client_id="mock_id",
    client_secret="mock_sec",
    scopes=[
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/userinfo.email"
    ]
)
gcal.save_token("scope_test_user", old_creds)
mismatch, missing = gcal.has_scope_mismatch("scope_test_user")
print(f"3a. has_scope_mismatch detected: {mismatch}, missing: {missing}")
assert mismatch == True, "has_scope_mismatch must detect missing openid scope"
assert "openid" in missing

# Calling load_token should invalidate the old token and return None
loaded = gcal.load_token("scope_test_user")
print(f"3b. load_token after scope mismatch: {loaded}")
assert loaded is None, "load_token must invalidate outdated token and return None"
assert gcal.is_connected("scope_test_user") == False, "Must require re-authentication"

# 4. Regenerate token with all 3 updated scopes
new_creds = Credentials(
    token="tok_new",
    refresh_token="ref_new",
    token_uri="https://oauth2.googleapis.com/token",
    client_id="mock_id",
    client_secret="mock_sec",
    scopes=gcal.SCOPES,
    id_token={"email": "student@studymind.ai", "sub": "1001"}
)
gcal.save_token("scope_test_user", new_creds)
loaded_new = gcal.load_token("scope_test_user")
print(f"4. Re-authenticated with new scopes: is_connected={gcal.is_connected('scope_test_user')}")
assert loaded_new is not None, "Regenerated token with new scopes must load successfully"
assert gcal.is_connected("scope_test_user") == True

# 5. OpenID id_token email retrieval
email = gcal.get_connected_account_email("scope_test_user")
print(f"5. Email extracted via OpenID id_token claims: {email}")
assert email == "student@studymind.ai", f"Expected student@studymind.ai, got {email}"

# 6. Cleanup
gcal.delete_token("scope_test_user")
print("6. Cleanup complete")

print("\nALL GOOGLE OAUTH SCOPES & RE-AUTHENTICATION TESTS PASSED! ✅")

