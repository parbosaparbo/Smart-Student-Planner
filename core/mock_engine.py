"""
StudyMind AI — High-Performance Mock Exam Engine
Batches and caches syllabus-grounded questions across selected topics with strict schema validation.
"""
import time
from typing import Dict, Any, List
from core.quiz_engine import generate_fast_quiz, validate_and_repair_questions


def generate_mock_exam_questions(
    selected_topics: List[Dict[str, Any]],
    total_questions: int = 10,
    difficulty: int = 3,
) -> Dict[str, Any]:
    """
    Generates syllabus-grounded mock exam questions across selected topics:
    - Distributes question count evenly across chosen topics.
    - Uses quiz_engine with cache & schema verification.
    - Logs execution time.
    """
    t0 = time.time()
    if not selected_topics:
        return {"questions": [], "execution_time_seconds": 0.0}

    num_topics = len(selected_topics)
    q_per_topic = max(1, total_questions // num_topics)

    all_questions = []

    for t in selected_topics:
        t_id = t.get("id", "t1")
        t_title = t.get("title", t_id)
        # Use fast cached quiz generator
        quiz_data = generate_fast_quiz(
            topic_id=t_id,
            topic_title=t_title,
            num_questions=q_per_topic,
            difficulty=difficulty,
        )
        qs = quiz_data.get("questions", [])
        for q in qs:
            q["topic_id"] = t_id
            q["topic_title"] = t_title
        all_questions.extend(qs)

    # Trim or fill to match requested count
    final_questions = all_questions[:total_questions]
    elapsed = round(time.time() - t0, 3)

    print(f"[MOCK EXAM ENGINE] Assembled {len(final_questions)} questions across {num_topics} topics in {elapsed}s")

    return {
        "questions": final_questions,
        "total_questions": len(final_questions),
        "difficulty": difficulty,
        "execution_time_seconds": elapsed,
    }

