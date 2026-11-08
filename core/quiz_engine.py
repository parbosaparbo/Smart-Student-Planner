"""
StudyMind AI — Ultra-Fast Quiz Generation Engine
Generates exactly 5 high-yield, scenario-based active recall MCQs in under 2 seconds.
"""
import json
from typing import Dict, Any
from gemini_client import call_gemini_json
from prompts import quiz_generator_prompt


def generate_fast_quiz(
    topic_id: str,
    topic_title: str,
    num_questions: int = 5,
    difficulty: int = 3,
) -> Dict[str, Any]:
    """
    Sub-2-second quiz generation:
    - Exactly 5 high-yield scenario MCQs
    - max_output_tokens=1024, temperature=0.2, response_mime_type='application/json'
    - Concise questions (<25 words) and single-sentence explanations
    """
    # Strict 5 questions batch size for maximum generation velocity
    target_q = min(max(num_questions, 3), 5)
    prompt = quiz_generator_prompt(
        topic_id=topic_id,
        topic_title=topic_title,
        num_questions=target_q,
        difficulty=difficulty,
    )
    
    # Fast constrained JSON generation
    quiz_data = call_gemini_json(
        prompt=prompt,
        temperature=0.2,
        max_tokens=1024,
    )
    
    # Ensure time limit and question count defaults
    if "time_limit_seconds" not in quiz_data:
        quiz_data["time_limit_seconds"] = len(quiz_data.get("questions", [])) * 60
        
    return quiz_data

