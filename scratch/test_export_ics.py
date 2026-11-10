import sys, json
sys.path.append(r'C:\\Users\\deshr\\Documents\\STUDY PLANNER 7 TH SEM')
import google_calendar as gcal
schedule = {
    "daily_blocks": [
        {
            "date": "2024-01-01",
            "day_type": "study",
            "blocks": [
                {
                    "topic_title": "Math",
                    "start_time": "09:00",
                    "duration_minutes": 60,
                    "topic_id": "t1",
                    "block_type": "normal",
                    "session_goal": "Complete chapter"
                },
                {
                    "topic_title": "Physics",
                    "start_time": "10:15",
                    "duration_minutes": 45,
                    "topic_id": "t2",
                    "block_type": "revision",
                    "session_goal": "Review concepts"
                }
            ]
        }
    ]
}
ics = gcal.export_schedule_to_ics(schedule, student_name='Test Student')
print(ics)

