"""
StudyMind AI — Weak Topic Manager & Spaced Revision Rescheduler
Handles:
1. Multi-source analysis (Quizzes + Mock Exams)
2. Topic-wise accuracy & repeated mistake tracking
3. Priority-based spaced revision rescheduling (Days +1/+2 and Days +4/+5)
4. Non-disturbance of completed past study sessions
5. Student availability & blocked day compliance
6. Revision completion tracking & mastery improvement delta
"""
from datetime import date, datetime, timedelta
import copy
from typing import Dict, Any, List, Optional, Tuple


def extract_topic_performance(
    quiz_results: List[Dict[str, Any]],
    mock_evaluation: Optional[Dict[str, Any]] = None,
    mock_results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Consolidates quiz and mock exam results to track topic-wise accuracy and repeated mistakes.
    Returns:
    {
        topic_id: {
            "topic_id": str,
            "topic_title": str,
            "attempts": int,
            "scores": List[float],
            "average_accuracy": float,
            "recent_accuracy": float,
            "repeated_mistakes_count": int,
            "missed_concepts": List[str],
            "urgency": "critical" | "weak" | "improving" | "mastered",
            "last_tested": str,
        }
    }
    """
    topics_map: Dict[str, Dict[str, Any]] = {}

    # 1. Process Quizzes
    for q in (quiz_results or []):
        tid = str(q.get("topic_id") or q.get("topic_title") or "unknown").strip()
        title = q.get("topic_title") or tid
        score = float(q.get("score_pct", 0))

        if tid not in topics_map:
            topics_map[tid] = {
                "topic_id": tid,
                "topic_title": title,
                "attempts": 0,
                "scores": [],
                "repeated_mistakes_count": 0,
                "missed_concepts": [],
                "questions_wrong": 0,
                "questions_total": 0,
            }

        t_entry = topics_map[tid]
        t_entry["attempts"] += 1
        t_entry["scores"].append(score)
        if score < 70:
            t_entry["repeated_mistakes_count"] += 1

        # Track missed concepts if available
        questions = q.get("questions", [])
        answers = q.get("answers", {})
        for idx, ques in enumerate(questions):
            qid = ques.get("id", f"q{idx+1}")
            correct = str(ques.get("correct_answer", "")).strip()
            given = str(answers.get(qid, "")).strip()
            t_entry["questions_total"] += 1
            if given != correct:
                t_entry["questions_wrong"] += 1
                concept = ques.get("explanation") or ques.get("question", "")[:60]
                if concept and concept not in t_entry["missed_concepts"]:
                    t_entry["missed_concepts"].append(concept[:80])

    # 2. Process Mock Evaluation topic_performance
    if mock_evaluation and isinstance(mock_evaluation, dict):
        topic_perf = mock_evaluation.get("topic_performance", [])
        for tp in topic_perf:
            tid = str(tp.get("topic_id") or "mock_topic").strip()
            title = tp.get("topic_id") or tid
            score = float(tp.get("score_pct", 0))

            if tid not in topics_map:
                topics_map[tid] = {
                    "topic_id": tid,
                    "topic_title": title,
                    "attempts": 0,
                    "scores": [],
                    "repeated_mistakes_count": 0,
                    "missed_concepts": [],
                    "questions_wrong": 0,
                    "questions_total": 0,
                }
            t_entry = topics_map[tid]
            t_entry["attempts"] += 1
            t_entry["scores"].append(score)
            if score < 70 or tp.get("verdict") in ("weak", "critical"):
                t_entry["repeated_mistakes_count"] += 1
            action = tp.get("priority_action", "")
            if action and action not in t_entry["missed_concepts"]:
                t_entry["missed_concepts"].append(action)

    # 3. Process additional Mock Results if any
    for mr in (mock_results or []):
        tid = str(mr.get("topic_id") or mr.get("subject") or "mock").strip()
        score = float(mr.get("score_pct", 0))
        if tid in topics_map:
            topics_map[tid]["attempts"] += 1
            topics_map[tid]["scores"].append(score)
            if score < 70:
                topics_map[tid]["repeated_mistakes_count"] += 1

    # 4. Final calculation: average accuracy & urgency classification
    results = {}
    for tid, data in topics_map.items():
        scores = data["scores"]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
        recent_score = scores[-1] if scores else 0.0

        # Urgency determination
        if recent_score < 50 or data["repeated_mistakes_count"] >= 2:
            urgency = "critical"
        elif recent_score < 70:
            urgency = "weak"
        elif len(scores) > 1 and recent_score > scores[0]:
            urgency = "improving"
        else:
            urgency = "mastered"

        improvement = round(recent_score - scores[0], 1) if len(scores) > 1 else 0.0

        results[tid] = {
            "topic_id": tid,
            "topic_title": data["topic_title"],
            "attempts": data["attempts"],
            "scores": scores,
            "average_accuracy": avg_score,
            "recent_accuracy": recent_score,
            "repeated_mistakes_count": data["repeated_mistakes_count"],
            "missed_concepts": data["missed_concepts"][:4],
            "urgency": urgency,
            "improvement_pct": improvement,
        }

    return results


def identify_weak_topics(
    quiz_results: List[Dict[str, Any]],
    mock_evaluation: Optional[Dict[str, Any]] = None,
    threshold: float = 70.0,
) -> List[Dict[str, Any]]:
    """
    Returns sorted list of weak topics prioritized by:
    1. Lowest recent score (< 50% first)
    2. Highest repeated mistakes count
    """
    performance = extract_topic_performance(quiz_results, mock_evaluation)
    weak_list = []

    for tid, info in performance.items():
        if info["recent_accuracy"] < threshold or info["repeated_mistakes_count"] > 0:
            weak_list.append(info)

    # Priority sort: Highest urgency, lowest accuracy, highest repeated mistakes
    urgency_rank = {"critical": 0, "weak": 1, "improving": 2, "mastered": 3}
    weak_list.sort(
        key=lambda x: (
            urgency_rank.get(x["urgency"], 9),
            x["recent_accuracy"],
            -x["repeated_mistakes_count"]
        )
    )
    return weak_list


def schedule_spaced_revisions(
    current_schedule: Dict[str, Any],
    weak_topics: List[Dict[str, Any]],
    student_profile: Dict[str, Any],
    today_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Generates a spaced revision plan:
    - Spacing algorithm:
        Round 1: 1-2 days after today (Active Retrieval)
        Round 2: 4-6 days after today (Delayed Spaced Consolidation)
    - Non-disturbance: Past sessions (date < today) are untouched.
    - Availability compliance: Respects daily_hours limit and blocked_days.
    - Returns proposal dict with changes and updated schedule.
    """
    if today_date is None:
        today_date = date.today()

    today_str = today_date.strftime("%Y-%m-%d")
    daily_hours = float(student_profile.get("daily_hours", 4.0))
    max_daily_minutes = int(daily_hours * 60)
    blocked_days = [str(b).lower() for b in student_profile.get("blocked_days", ["sunday"])]
    pref_times = student_profile.get("preferred_times", ["morning", "evening"])

    # Determine default revision start time
    time_slot = "10:00"
    if "early_morning" in pref_times:
        time_slot = "07:00"
    elif "evening" in pref_times:
        time_slot = "18:00"
    elif "night" in pref_times:
        time_slot = "20:30"

    updated_schedule = copy.deepcopy(current_schedule)
    daily_blocks = updated_schedule.get("daily_blocks", [])

    # Index existing days by date
    days_by_date = {d.get("date"): d for d in daily_blocks if d.get("date")}

    changes_applied = []
    blocks_added = 0

    for topic in weak_topics:
        tid = topic.get("topic_id", "topic")
        title = topic.get("topic_title", tid)
        urgency = topic.get("urgency", "weak")
        mistakes = topic.get("repeated_mistakes_count", 0)

        # Spaced intervals:
        # Round 1 (1-2 days out)
        # Round 2 (4-6 days out for critical topics or repeated mistakes)
        intervals = [1]
        if urgency == "critical" or mistakes >= 2:
            intervals.append(4)

        for round_num, days_ahead in enumerate(intervals, 1):
            target_date = today_date + timedelta(days=days_ahead)

            # Ensure not a blocked day
            while target_date.strftime("%A").lower() in blocked_days:
                target_date += timedelta(days=1)

            date_str = target_date.strftime("%Y-%m-%d")

            # Check day capacity
            day_data = days_by_date.get(date_str)
            if not day_data:
                day_data = {"date": date_str, "day_type": "revision", "blocks": []}
                daily_blocks.append(day_data)
                days_by_date[date_str] = day_data

            current_minutes = sum(int(b.get("duration_minutes", 60)) for b in day_data.get("blocks", []))

            # Determine duration based on urgency
            duration = 60 if urgency == "critical" else 45
            if current_minutes + duration > max_daily_minutes:
                # Scale down duration to fit student's limit or shift to next day
                duration = max(30, max_daily_minutes - current_minutes)

            # Check if this topic is already scheduled on this day
            already_scheduled = any(
                b.get("topic_id") == tid and b.get("is_revision")
                for b in day_data.get("blocks", [])
            )
            if already_scheduled:
                continue

            rev_goal = (
                f"Spaced Recall R{round_num}: Fix repeated mistakes in {title}"
                if mistakes > 0
                else f"Spaced Revision R{round_num}: Reinforce weak spots in {title}"
            )

            rev_block = {
                "topic_id": tid,
                "topic_title": f"🔄 Revision: {title}",
                "start_time": time_slot,
                "duration_minutes": duration,
                "session_goal": rev_goal,
                "resources_tip": f"Feynman technique: explain core concepts of {title} without looking at notes.",
                "is_revision": True,
                "revision_round": round_num,
                "urgency": urgency,
            }

            day_data.setdefault("blocks", []).append(rev_block)
            if day_data.get("day_type") == "rest":
                day_data["day_type"] = "revision"

            blocks_added += 1
            changes_applied.append({
                "action": "add",
                "topic_id": tid,
                "topic_title": title,
                "new_date": date_str,
                "new_time": time_slot,
                "duration_minutes": duration,
                "round": round_num,
                "reason": f"Spaced revision (accuracy {topic.get('recent_accuracy',0)}%, {mistakes} repeated mistakes)",
            })

    # Sort daily blocks chronologically
    daily_blocks.sort(key=lambda d: d.get("date", ""))
    updated_schedule["daily_blocks"] = daily_blocks

    return {
        "updated_schedule": updated_schedule,
        "changes": changes_applied,
        "blocks_added": blocks_added,
        "total_weak_topics_handled": len(weak_topics),
        "hitl_message": (
            f"StudyMind AI has prepared {blocks_added} spaced revision sessions for "
            f"{len(weak_topics)} weak topic(s) prioritizing lowest accuracy and repeated errors. "
            f"Already completed sessions have been preserved intact."
        ),
    }

