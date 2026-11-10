"""
StudyMind AI — Weak Topic Manager & Spaced Revision Rescheduler
Handles:
1. Multi-source analysis (Quizzes + Mock Exams)
2. Topic-wise accuracy & repeated mistake tracking
3. Priority-based spaced revision rescheduling (Days +1/+2 and Days +4/+5)
4. Non-disturbance of completed past study sessions
5. Capacity-aware shifting of future sessions without exceeding daily hours
6. Overlap-free sequential time allocation
7. Automatic Google Calendar synchronization & in-app schedule updates
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


def assign_non_overlapping_times(blocks: List[Dict[str, Any]], preferred_times: List[str]) -> None:
    """
    Assigns sequential, non-overlapping start and end times to all blocks on a day.
    Respects student's preferred study window and includes a 15-minute cognitive rest buffer.
    """
    base_slots = ["09:00", "11:30", "14:30", "17:30", "20:00"]
    if "early_morning" in preferred_times:
        base_slots = ["06:30", "08:30", "11:00", "15:00", "18:00"]
    elif "evening" in preferred_times or "night" in preferred_times:
        base_slots = ["10:00", "14:00", "17:30", "19:30", "21:30"]

    current_end_dt = None

    for idx, blk in enumerate(blocks):
        # Preserve completed blocks with their fixed times
        if blk.get("completed") and blk.get("start_time"):
            try:
                st_dt = datetime.strptime(blk["start_time"], "%H:%M")
                dur = int(blk.get("duration_minutes", 60))
                current_end_dt = st_dt + timedelta(minutes=dur)
                blk["end_time"] = current_end_dt.strftime("%H:%M")
                continue
            except Exception:
                pass

        dur = int(blk.get("duration_minutes", 60))
        default_start_str = base_slots[idx % len(base_slots)]
        default_start_dt = datetime.strptime(default_start_str, "%H:%M")

        if current_end_dt is None:
            assigned_start_dt = default_start_dt
        else:
            min_start_dt = current_end_dt + timedelta(minutes=15)
            if default_start_dt >= min_start_dt:
                assigned_start_dt = default_start_dt
            else:
                assigned_start_dt = min_start_dt

        blk["start_time"] = assigned_start_dt.strftime("%H:%M")
        current_end_dt = assigned_start_dt + timedelta(minutes=dur)
        blk["end_time"] = current_end_dt.strftime("%H:%M")


def recalculate_future_schedule(
    current_schedule: Dict[str, Any],
    weak_topics: List[Dict[str, Any]],
    student_profile: Dict[str, Any],
    today_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Recalculates the entire remaining future study schedule:
    1. Identifies weak topics and generates spaced revision sessions (Round 1: 1-2 days, Round 2: 4-6 days),
       prioritizing lowest scores first.
    2. Preserves all past sessions (date < today) and completed sessions.
    3. Inserts revision sessions on optimal future dates.
    4. Smoothly pushes uncompleted upcoming study blocks forward if daily capacity is exceeded.
    5. Assigns sequential, non-overlapping start/end times respecting student preferences.
    6. Never exceeds daily study-hour limits (daily_hours).
    7. Respects blocked days (e.g. Sunday).
    """
    if today_date is None:
        today_date = date.today()

    today_str = today_date.strftime("%Y-%m-%d")
    daily_hours = float((student_profile or {}).get("daily_hours", 4.0))
    max_daily_minutes = int(daily_hours * 60)
    blocked_days = [str(b).lower() for b in (student_profile or {}).get("blocked_days", ["sunday"])]
    pref_times = (student_profile or {}).get("preferred_times", ["morning", "evening"])

    # Sort weak topics: lowest score first, then highest repeated mistakes
    sorted_weaks = sorted(
        weak_topics,
        key=lambda w: (
            float(w.get("recent_accuracy", 100)),
            -int(w.get("repeated_mistakes_count", 0)),
            0 if w.get("urgency") == "critical" else 1
        )
    )

    orig_daily = copy.deepcopy(current_schedule.get("daily_blocks", []))

    # 1. Separate past days from future/today days
    past_days = [d for d in orig_daily if d.get("date", "") < today_str]
    future_days_orig = [d for d in orig_daily if d.get("date", "") >= today_str]

    # Map future dates to completed blocks and uncompleted study blocks
    existing_completed_by_date = {}
    uncompleted_study_blocks = []
    future_dates = []

    for d in future_days_orig:
        d_str = d.get("date")
        if d_str:
            future_dates.append(d_str)
            existing_completed_by_date[d_str] = [
                b for b in d.get("blocks", []) if b.get("completed")
            ]
            for b in d.get("blocks", []):
                if not b.get("completed") and not b.get("is_revision"):
                    uncompleted_study_blocks.append(b)

    # 2. Plan Spaced Revisions for Weak Topics
    revisions_by_date = {}
    changes_log = []

    for topic in sorted_weaks:
        tid = topic.get("topic_id", "topic")
        title = topic.get("topic_title", tid)
        score = float(topic.get("recent_accuracy", 0))
        urgency = topic.get("urgency", "weak")
        mistakes = int(topic.get("repeated_mistakes_count", 0))

        # Round 1: 1-2 days out
        # Round 2: 4-6 days out for critical (<50% or mistakes >= 2)
        intervals = [1]
        if score < 50 or urgency == "critical" or mistakes >= 2:
            intervals.append(4)

        for round_num, days_ahead in enumerate(intervals, 1):
            target_dt = today_date + timedelta(days=days_ahead)
            # Skip blocked days
            while target_dt.strftime("%A").lower() in blocked_days:
                target_dt += timedelta(days=1)

            target_date_str = target_dt.strftime("%Y-%m-%d")

            dur = 60 if urgency == "critical" or score < 50 else 45
            rev_block = {
                "topic_id": tid,
                "topic_title": f"🔄 Revision: {title}",
                "duration_minutes": dur,
                "session_goal": f"Spaced Revision R{round_num}: Recover weak concept in {title} (Score: {score}%)",
                "resources_tip": f"Active recall & Feynman explanation: teach {title} out loud.",
                "is_revision": True,
                "revision_round": round_num,
                "urgency": urgency,
            }
            revisions_by_date.setdefault(target_date_str, []).append(rev_block)
            changes_log.append({
                "action": "add_revision",
                "topic_id": tid,
                "topic_title": title,
                "date": target_date_str,
                "round": round_num,
                "duration_minutes": dur,
                "reason": f"Weak topic auto-reschedule (score {score}%)"
            })

    # 3. Assemble and pack future schedule starting from today
    recalculated_future_days = []
    current_dt = today_date
    uncompleted_pool = list(uncompleted_study_blocks)

    min_future_days = max(len(future_dates), 14)
    day_count = 0

    while (uncompleted_pool or day_count < min_future_days) and day_count < 60:
        d_str = current_dt.strftime("%Y-%m-%d")
        day_name = current_dt.strftime("%A").lower()
        day_count += 1

        is_blocked = day_name in blocked_days
        if is_blocked:
            recalculated_future_days.append({
                "date": d_str,
                "day_type": "rest",
                "blocks": []
            })
            current_dt += timedelta(days=1)
            continue

        day_blocks = []
        minutes_used = 0

        # a. Preserve any completed blocks on this date
        completed_here = existing_completed_by_date.get(d_str, [])
        for cb in completed_here:
            day_blocks.append(cb)
            minutes_used += int(cb.get("duration_minutes", 60))

        # b. Add scheduled revisions for this date
        revs_here = revisions_by_date.get(d_str, [])
        for rb in revs_here:
            dur = int(rb.get("duration_minutes", 45))
            if minutes_used + dur <= max_daily_minutes or not day_blocks:
                day_blocks.append(rb)
                minutes_used += dur
            else:
                # If day is full, push revision to next day
                next_day_str = (current_dt + timedelta(days=1)).strftime("%Y-%m-%d")
                revisions_by_date.setdefault(next_day_str, []).append(rb)

        # c. Fill remaining capacity with uncompleted regular study blocks
        while uncompleted_pool:
            next_study = uncompleted_pool[0]
            dur = int(next_study.get("duration_minutes", 60))
            if minutes_used + dur <= max_daily_minutes:
                day_blocks.append(uncompleted_pool.pop(0))
                minutes_used += dur
            else:
                # Push remaining upcoming blocks to subsequent days
                break

        # Assign non-overlapping times
        if day_blocks:
            assign_non_overlapping_times(day_blocks, pref_times)
            d_type = "revision" if any(b.get("is_revision") for b in day_blocks) else "study"
        else:
            d_type = "rest"

        recalculated_future_days.append({
            "date": d_str,
            "day_type": d_type,
            "blocks": day_blocks
        })

        current_dt += timedelta(days=1)

    # Combine past days (untouched) + recalculated future days
    final_daily = past_days + recalculated_future_days
    final_daily.sort(key=lambda d: d.get("date", ""))

    updated_schedule = copy.deepcopy(current_schedule)
    updated_schedule["daily_blocks"] = final_daily
    updated_schedule["last_rescheduled_at"] = datetime.now().isoformat()
    updated_schedule["total_study_blocks"] = sum(len(d.get("blocks", [])) for d in final_daily)
    updated_schedule["reschedule_summary"] = {
        "weak_topics_count": len(weak_topics),
        "revisions_added": len(changes_log),
        "changes": changes_log,
        "recalculated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    return {
        "status": "success",
        "updated_schedule": updated_schedule,
        "changes": changes_log,
        "weak_topics": sorted_weaks,
        "blocks_added": len(changes_log),
        "hitl_message": (
            f"StudyMind AI has recalculated your study plan, automatically inserting {len(changes_log)} "
            f"revision sessions for {len(weak_topics)} weak topic(s) prioritizing lowest scores. "
            f"All past records and completed sessions have been preserved intact."
        ),
    }


def schedule_spaced_revisions(
    current_schedule: Dict[str, Any],
    weak_topics: List[Dict[str, Any]],
    student_profile: Dict[str, Any],
    today_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Backwards-compatible wrapper calling the full recalculation engine.
    """
    return recalculate_future_schedule(current_schedule, weak_topics, student_profile, today_date)


def auto_reschedule_workflow(
    session_state: Dict[str, Any],
    student_name: str = "Student",
    today_date: Optional[date] = None,
    sync_gcal: bool = True,
) -> Dict[str, Any]:
    """
    Complete end-to-end automatic weak-topic rescheduling workflow:
    1. Analyzes latest quiz results & mock exam evaluations.
    2. Identifies weak topics (< 70% threshold).
    3. Recalculates the remaining future study schedule.
    4. Updates session state & saves persistent state.
    5. Syncs revised sessions to Google Calendar without creating duplicates.
    """
    from storage import save_persistent_state

    quiz_results = session_state.get("quiz_results", [])
    mock_eval = session_state.get("mock_evaluation")
    current_sched = session_state.get("schedule", {})
    student_prof = session_state.get("student_profile", {})

    if not current_sched or not current_sched.get("daily_blocks"):
        return {
            "status": "no_schedule",
            "message": "No active study schedule found. Please generate a schedule in Schedule Generator first.",
            "weak_topics": identify_weak_topics(quiz_results, mock_eval, threshold=70.0),
        }

    weak_topics = identify_weak_topics(quiz_results, mock_eval, threshold=70.0)
    if not weak_topics:
        return {
            "status": "no_weak_topics",
            "message": "All tested topics are above 70% threshold. No rescheduling required.",
            "weak_topics": [],
        }

    # Execute deterministic recalculation
    recalc_result = recalculate_future_schedule(
        current_schedule=current_sched,
        weak_topics=weak_topics,
        student_profile=student_prof,
        today_date=today_date,
    )

    updated_schedule = recalc_result["updated_schedule"]
    session_state["schedule"] = updated_schedule
    session_state["last_reschedule_result"] = recalc_result

    # Save to local persistence
    save_persistent_state(session_state)

    # Google Calendar synchronization (if connected)
    gcal_sync_result = None
    if sync_gcal:
        try:
            import google_calendar as gcal
            s_key = student_name or student_prof.get("student_name", "Student")
            if gcal.is_connected(s_key):
                gcal_sync_result = gcal.sync_schedule_to_calendar(updated_schedule, s_key, s_key)
                session_state["gcal_event_map"] = gcal_sync_result
                save_persistent_state(session_state)
        except Exception as gcal_err:
            gcal_sync_result = {"error": str(gcal_err)}

    recalc_result["gcal_sync_result"] = gcal_sync_result
    return recalc_result
