"""
Comprehensive test for export_schedule_to_ics and google_calendar module resilience.
Tests:
1. Normal function with multi-day schedule
2. Empty schedule (no blocks)
3. Rest-day skipping
4. Revision block labeling
5. Missing/invalid date fields (graceful degradation)
6. is_configured() / is_connected() return False gracefully (not raise)
7. Simulated missing-deps scenario via patching
"""
import sys, importlib
sys.path.insert(0, r'C:\Users\deshr\Documents\STUDY PLANNER 7 TH SEM')

import google_calendar as gcal

PASS = 0
FAIL = 0

def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        print(f"  ✅ PASS: {label}")
        PASS += 1
    else:
        print(f"  ❌ FAIL: {label}" + (f" — {detail}" if detail else ""))
        FAIL += 1

print("\n=== 1. Normal multi-day schedule ===")
schedule = {
    "daily_blocks": [
        {
            "date": "2026-11-15",
            "day_type": "study",
            "blocks": [
                {"topic_title": "OS Concepts", "start_time": "09:00", "duration_minutes": 90,
                 "topic_id": "os_01", "block_type": "normal", "session_goal": "Chapter 1"},
                {"topic_title": "Networking", "start_time": "11:00", "duration_minutes": 60,
                 "topic_id": "net_01", "block_type": "normal", "session_goal": "OSI Model"},
            ]
        },
        {
            "date": "2026-11-16",
            "day_type": "rest",
            "blocks": []
        },
        {
            "date": "2026-11-17",
            "day_type": "revision",
            "blocks": [
                {"topic_title": "OS Concepts", "start_time": "10:00", "duration_minutes": 45,
                 "topic_id": "os_01", "block_type": "revision", "session_goal": "Revise"},
            ]
        }
    ]
}
result = gcal.export_schedule_to_ics(schedule, student_name="Desh")
check("Returns string", isinstance(result, str))
check("Has VCALENDAR", "BEGIN:VCALENDAR" in result)
check("Has VEVENT", "BEGIN:VEVENT" in result)
check("Has OS Concepts", "OS Concepts" in result)
check("Has Networking", "Networking" in result)
check("Rest day skipped (no rest block)", result.count("BEGIN:VEVENT") == 3,
      f"VEVENT count: {result.count('BEGIN:VEVENT')}")
check("Revision block uses 🔄 emoji", "🔄 OS Concepts [Revision]" in result)
check("Study block uses 📚 emoji", "📚 OS Concepts" in result or "📚 Networking" in result)
check("Has VALARM", "BEGIN:VALARM" in result)
check("Ends with VCALENDAR", "END:VCALENDAR" in result)

print("\n=== 2. Empty schedule ===")
empty = gcal.export_schedule_to_ics({}, student_name="Empty")
check("Empty returns string", isinstance(empty, str))
check("Has VCALENDAR even when empty", "BEGIN:VCALENDAR" in empty)
check("No VEVENT when empty", "BEGIN:VEVENT" not in empty)

print("\n=== 3. All rest days ===")
rest_only = {"daily_blocks": [
    {"date": "2026-11-20", "day_type": "rest", "blocks": []},
    {"date": "2026-11-21", "day_type": "rest", "blocks": []},
]}
rest_result = gcal.export_schedule_to_ics(rest_only, "Student")
check("Rest-only: no VEVENT", "BEGIN:VEVENT" not in rest_result)

print("\n=== 4. Missing/invalid fields ===")
bad_schedule = {"daily_blocks": [
    {
        "date": "",           # empty date
        "day_type": "study",
        "blocks": [
            {"topic_title": "", "start_time": "INVALID", "duration_minutes": "not_a_number",
             "topic_id": "", "block_type": "normal", "session_goal": ""}
        ]
    }
]}
try:
    bad_result = gcal.export_schedule_to_ics(bad_schedule, "Test")
    check("Invalid fields: does not crash", True)
    check("Invalid fields: returns string", isinstance(bad_result, str))
except Exception as e:
    check("Invalid fields: does not crash", False, str(e))

print("\n=== 5. is_configured / is_connected return bool (not raise) ===")
try:
    cfg = gcal.is_configured()
    check("is_configured() returns bool", isinstance(cfg, bool))
except Exception as e:
    check("is_configured() returns bool", False, str(e))

try:
    conn = gcal.is_connected("nonexistent_user_xyz")
    check("is_connected() returns bool", isinstance(conn, bool))
except Exception as e:
    check("is_connected() returns bool", False, str(e))

print("\n=== 6. Simulated missing deps: _GCAL_DEPS_AVAILABLE=False ===")
original_avail = gcal._GCAL_DEPS_AVAILABLE
try:
    gcal._GCAL_DEPS_AVAILABLE = False
    cfg2 = gcal.is_configured()
    check("is_configured() returns False when deps missing", cfg2 == False)
    conn2 = gcal.is_connected("any")
    check("is_connected() returns False when deps missing", conn2 == False)
    # export_schedule_to_ics must still work (stdlib only)
    ics2 = gcal.export_schedule_to_ics(schedule, "NoDeps")
    check("export_schedule_to_ics works without deps", "BEGIN:VCALENDAR" in ics2)
finally:
    gcal._GCAL_DEPS_AVAILABLE = original_avail

print("\n=== 7. UID uniqueness ===")
same_sched = {"daily_blocks": [
    {"date": "2026-12-01", "day_type": "study", "blocks": [
        {"topic_title": "A", "start_time": "09:00", "duration_minutes": 60, "topic_id": "t1", "block_type": "normal", "session_goal": ""},
        {"topic_title": "B", "start_time": "10:15", "duration_minutes": 60, "topic_id": "t2", "block_type": "normal", "session_goal": ""},
    ]}
]}
uid_result = gcal.export_schedule_to_ics(same_sched, "X")
uids = [line.split("UID:")[1].strip() for line in uid_result.split("\r\n") if line.startswith("UID:")]
check("UIDs are unique", len(uids) == len(set(uids)), f"UIDs: {uids}")

print(f"\n{'='*50}")
print(f"Results: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)

