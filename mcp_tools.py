"""
StudyMind AI — MCP Tools Module
Implements the 5 tools available to StudyMind AI:
  1. generate_quiz(topic_id, num_questions)
  2. reschedule_weak_topic(topic_id, reason)
  3. search_syllabus(query)
  4. push_to_calendar(study_block_id)
  5. analyze_weak_spots(student_id)
"""
import json
from typing import Any, Dict, List, Optional
from gemini_client import call_gemini_json
from prompts import quiz_generator_prompt, smart_rescheduler_prompt, weak_spot_analyzer_prompt


def generate_quiz(topic_id: str, num_questions: int = 5, difficulty: int = 3, topic_title: str = "") -> Dict[str, Any]:
    """
    MCP Tool: generate_quiz
    Creates a fresh scenario-based AI quiz for a topic.
    """
    prompt = quiz_generator_prompt(topic_id, topic_title or topic_id, num_questions, difficulty)
    return call_gemini_json(prompt, temperature=0.6)


def reschedule_weak_topic(topic_id: str, reason: str, current_schedule: dict, student_name: str = "Student") -> Dict[str, Any]:
    """
    MCP Tool: reschedule_weak_topic
    Adjusts the student's study plan to surgically insert revision blocks for a weak topic.
    """
    weak_spots = [{"topic_id": topic_id, "topic_title": topic_id, "urgency": "critical", "root_cause": reason}]
    prompt = smart_rescheduler_prompt(current_schedule, weak_spots, student_name)
    return call_gemini_json(prompt, temperature=0.3)


def search_syllabus(query: str, topic_tree: dict) -> List[Dict[str, Any]]:
    """
    MCP Tool: search_syllabus
    RAG-style semantic search over the student's uploaded syllabus.
    Finds relevant topics and subtopics matching the query.
    """
    query_lower = query.lower()
    matches = []

    for topic in topic_tree.get("topics", []):
        score = 0
        title = topic.get("title", "").lower()
        if query_lower in title:
            score += 3

        # Check subtopics
        sub_matches = []
        for sub in topic.get("subtopics", []):
            sub_title = sub.get("title", "").lower()
            concepts  = [c.lower() for c in sub.get("key_concepts", [])]
            if query_lower in sub_title or any(query_lower in c for c in concepts):
                score += 2
                sub_matches.append(sub)

        if score > 0:
            matches.append({
                "topic_id":    topic.get("id"),
                "title":       topic.get("title"),
                "difficulty":  topic.get("difficulty"),
                "priority":    topic.get("priority"),
                "relevance":   score,
                "matched_subtopics": sub_matches,
            })

    # Sort by relevance descending
    matches.sort(key=lambda x: x["relevance"], reverse=True)
    return matches


def push_to_calendar(study_block: dict) -> Dict[str, Any]:
    """
    MCP Tool: push_to_calendar
    Generates a Google Calendar event URL and iCal/JSON format
    for a study block to allow 1-click sync.
    """
    from urllib.parse import quote

    title       = f"📚 Study: {study_block.get('topic_title', 'Session')}"
    description = f"Goal: {study_block.get('session_goal','')}\nTip: {study_block.get('resources_tip','')}"
    date_str    = study_block.get("date", "")
    time_str    = study_block.get("start_time", "09:00").replace(":", "")

    # Rough RFC 5545 format
    start_dt = f"{date_str.replace('-','')}T{time_str}00"

    gcal_url = (
        f"https://calendar.google.com/calendar/render?action=TEMPLATE"
        f"&text={quote(title)}"
        f"&details={quote(description)}"
        f"&dates={start_dt}/{start_dt}"
    )

    return {
        "status": "ready",
        "study_block_id": study_block.get("topic_id", "block"),
        "google_calendar_url": gcal_url,
        "event_summary": title,
    }


def analyze_weak_spots(quiz_results: list, student_name: str = "Student") -> Dict[str, Any]:
    """
    MCP Tool: analyze_weak_spots
    Returns a full mastery breakdown, blind spots, and personalized recovery plan.
    """
    prompt = weak_spot_analyzer_prompt(quiz_results, student_name)
    return call_gemini_json(prompt, temperature=0.3)



def apply_schedule_changes(schedule: dict, changes: list) -> dict:
    """
    Applies surgical reschedule changes (add, move, remove) to the daily_blocks schedule.
    """
    import copy
    updated = copy.deepcopy(schedule)
    daily = updated.get("daily_blocks", [])

    for ch in changes:
        action = ch.get("action", "").lower()
        t_id = ch.get("topic_id", "")
        new_date = ch.get("new_date")
        orig_date = ch.get("original_date")

        if action == "remove" and orig_date:
            for day in daily:
                if day.get("date") == orig_date:
                    day["blocks"] = [b for b in day.get("blocks", []) if b.get("topic_id") != t_id]

        elif action == "add" and new_date:
            new_block = {
                "topic_id": t_id,
                "topic_title": f"Revision: {t_id.upper()}",
                "start_time": ch.get("new_time") or "10:00",
                "duration_minutes": ch.get("duration_minutes") or 60,
                "session_goal": f"Active revision and gap recovery for {t_id} ({ch.get('reason','')})",
                "resources_tip": "Focus on high-leverage practice problems and Feynman recall.",
            }
            # Find or insert day
            day_match = next((d for d in daily if d.get("date") == new_date), None)
            if day_match:
                day_match.setdefault("blocks", []).append(new_block)
            else:
                daily.append({
                    "date": new_date,
                    "day_type": "revision",
                    "blocks": [new_block]
                })

        elif action == "move":
            moved_block = None
            if orig_date:
                for day in daily:
                    if day.get("date") == orig_date:
                        for b in day.get("blocks", []):
                            if b.get("topic_id") == t_id:
                                moved_block = b
                                break
                        day["blocks"] = [b for b in day.get("blocks", []) if b.get("topic_id") != t_id]
            if not moved_block:
                moved_block = {
                    "topic_id": t_id,
                    "topic_title": t_id,
                    "start_time": ch.get("new_time") or "10:00",
                    "duration_minutes": ch.get("duration_minutes") or 60,
                    "session_goal": ch.get("reason", "Rescheduled session"),
                    "resources_tip": "Review core concepts first.",
                }
            if ch.get("new_time"):
                moved_block["start_time"] = ch["new_time"]
            if new_date:
                day_match = next((d for d in daily if d.get("date") == new_date), None)
                if day_match:
                    day_match.setdefault("blocks", []).append(moved_block)
                else:
                    daily.append({
                        "date": new_date,
                        "day_type": "revision",
                        "blocks": [moved_block]
                    })

    # Keep days sorted
    daily.sort(key=lambda d: d.get("date", ""))
    updated["daily_blocks"] = daily
    return updated
