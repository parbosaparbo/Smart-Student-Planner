import sys, py_compile
sys.path.insert(0, r'C:\Users\deshr\Documents\STUDY PLANNER 7 TH SEM')

# Force recompile from source
src = r'C:\Users\deshr\Documents\STUDY PLANNER 7 TH SEM\google_calendar.py'
try:
    py_compile.compile(src, doraise=True)
    print("COMPILED OK")
except py_compile.PyCompileError as e:
    print(f"COMPILE ERROR: {e}")
    sys.exit(1)

import google_calendar as gcal
fn = getattr(gcal, 'export_schedule_to_ics', None)
print("FUNCTION:", "FOUND" if fn else "MISSING")
print("TYPE:", type(fn))

if fn:
    # Quick functional test
    schedule = {
        "daily_blocks": [
            {
                "date": "2024-01-15",
                "day_type": "study",
                "blocks": [
                    {
                        "topic_title": "Data Structures",
                        "start_time": "09:00",
                        "duration_minutes": 90,
                        "topic_id": "topic_ds_01",
                        "block_type": "normal",
                        "session_goal": "Complete chapter on linked lists"
                    }
                ]
            },
            {
                "date": "2024-01-16",
                "day_type": "rest",
                "blocks": []
            }
        ]
    }
    result = gcal.export_schedule_to_ics(schedule, student_name="Riya")
    print("ICS LENGTH:", len(result))
    print("HAS VCALENDAR:", "BEGIN:VCALENDAR" in result)
    print("HAS VEVENT:", "BEGIN:VEVENT" in result)
    print("HAS DATA STRUCTURES:", "Data Structures" in result)
    print("\n--- FIRST 500 CHARS ---")
    print(result[:500])

