"""
StudyMind AI — Official MCP (Model Context Protocol) Server
Exposes both core study planner tools and multi-tier PDF syllabus parsing tools
using the official Python MCP Server framework (mcp >= 2.0.0).

Can be run:
1. In-process via MCPClient / Python import for fast native desktop & Streamlit usage.
2. Standalone over stdio for external MCP clients (Claude, Cursor, custom agents):
   $ python mcp_server.py
"""
import asyncio
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

try:
    import pymupdf4llm
except ImportError:
    pymupdf4llm = None

from mcp.server.mcpserver import MCPServer

# Initialize the official MCP Server
server = MCPServer("StudyMind-AI-MCP")

# ═══════════════════════════════════════════════════════════════════════════════
# 1. CORE MCP TOOLS (Preserved & Enhanced)
# ═══════════════════════════════════════════════════════════════════════════════

@server.tool(
    name="generate_quiz",
    description="Generates scenario-based active recall quiz MCQs accepting syllabus context, topic, difficulty, and question count with caching and schema validation.",
)
def generate_quiz(
    topic: str = "",
    topic_id: str = "t1",
    difficulty: int = 3,
    question_count: int = 5,
    syllabus_context: str = "",
    topic_title: str = "",
    num_questions: int = 5,
    bypass_cache: bool = False,
) -> Dict[str, Any]:
    """MCP Tool: Fast cached scenario-based AI quiz generation using Gemini + Python schema validation."""
    from core.quiz_engine import generate_fast_quiz
    actual_title = topic_title or topic or topic_id
    actual_count = question_count if question_count != 5 or num_questions == 5 else num_questions
    return generate_fast_quiz(
        topic_id=topic_id,
        topic_title=actual_title,
        num_questions=actual_count,
        difficulty=difficulty,
        syllabus_context=syllabus_context,
        bypass_cache=bypass_cache,
        topic=actual_title,
        question_count=actual_count,
    )


@server.tool(
    name="generate_study_schedule",
    description="Generates an optimized day-by-day study schedule adhering to the 70/20/10 rule with Python-first speed.",
)
def generate_study_schedule(student_profile: dict, topic_tree: dict, today_str: str = "") -> Dict[str, Any]:
    """MCP Tool: Sub-second deterministic hybrid study planner."""
    from core.scheduler import generate_fast_schedule
    from datetime import date
    if not today_str:
        today_str = str(date.today())
    return generate_fast_schedule(student_profile, topic_tree, today_str)


@server.tool(
    name="generate_mock_exam",
    description="Generates syllabus-grounded, timed mock exam MCQs across multiple topics with strict schema validation.",
)
def generate_mock_exam(selected_topics: list, total_questions: int = 10, difficulty: int = 3) -> Dict[str, Any]:
    """MCP Tool: Multi-topic mock exam generator."""
    from core.mock_engine import generate_mock_exam_questions
    return generate_mock_exam_questions(selected_topics, total_questions, difficulty)


@server.tool(
    name="reschedule_weak_topic",
    description="Surgically recalculates and inserts revision blocks into a study schedule for topics below 70% mastery.",
)
def reschedule_weak_topic(
    topic_id: str,
    reason: str,
    current_schedule: dict,
    student_name: str = "Student",
) -> Dict[str, Any]:
    """MCP Tool: Adjusts student study plan to surgically insert revision blocks."""
    from prompts import smart_rescheduler_prompt
    from gemini_client import call_gemini_json

    weak_spots = [{
        "topic_id": topic_id,
        "topic_title": topic_id,
        "urgency": "critical",
        "root_cause": reason,
    }]
    prompt = smart_rescheduler_prompt(current_schedule, weak_spots, student_name)
    return call_gemini_json(prompt, temperature=0.3)


@server.tool(
    name="search_syllabus",
    description="Context-aware RAG engine retrieving high-relevance syllabus chunks for chatbot and question generation.",
)
def search_syllabus(query: str, topic_tree: dict) -> List[Dict[str, Any]]:
    """MCP Tool: High-performance RAG retriever over syllabus topic hierarchy."""
    from core.rag_engine import get_syllabus_rag
    rag = get_syllabus_rag(topic_tree)
    chunks = rag.retrieve(query, top_k=4)
    if chunks:
        return chunks

    query_lower = query.lower().strip()
    if not query_lower:
        return []

    matches = []
    for topic in topic_tree.get("topics", []):
        score = 0
        title = topic.get("title", "").lower()
        if query_lower in title:
            score += 4

        sub_matches = []
        for sub in topic.get("subtopics", []):
            sub_title = sub.get("title", "").lower()
            concepts = [str(c).lower() for c in sub.get("key_concepts", [])]
            if query_lower in sub_title:
                score += 3
                sub_matches.append(sub)
            elif any(query_lower in c for c in concepts):
                score += 2
                sub_matches.append(sub)

        if score > 0:
            matches.append({
                "topic_id": topic.get("id"),
                "title": topic.get("title"),
                "difficulty": topic.get("difficulty"),
                "priority": topic.get("priority"),
                "relevance": score,
                "text": f"{topic.get('title')}: {', '.join(s.get('title','') for s in sub_matches)}",
                "matched_subtopics": sub_matches,
                "is_elective": topic.get("is_elective", False),
            })

    matches.sort(key=lambda x: x["relevance"], reverse=True)
    return matches


@server.tool(
    name="push_to_calendar",
    description="Generates Google Calendar URL and metadata for a 1-click sync of a study block.",
)
def push_to_calendar(study_block: dict) -> Dict[str, Any]:
    """MCP Tool: Generates Google Calendar event URL and RFC 5545 format."""
    from urllib.parse import quote

    title = f"📚 Study: {study_block.get('topic_title', 'Session')}"
    description = f"Goal: {study_block.get('session_goal','')}\nTip: {study_block.get('resources_tip','')}"
    date_str = study_block.get("date", "")
    time_str = str(study_block.get("start_time", "09:00")).replace(":", "")

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


@server.tool(
    name="analyze_weak_spots",
    description="Audits student quiz and mock exam history to detect critical gaps (<50%), repeated mistakes, and dangerous blind spots.",
)
def analyze_weak_spots(quiz_results: list, student_name: str = "Student", mock_evaluation: dict = None) -> Dict[str, Any]:
    """MCP Tool: Analyzes mastery breakdown, repeated mistakes, and blind spots."""
    from prompts import weak_spot_analyzer_prompt
    from gemini_client import call_gemini_json
    from core.weak_topic_manager import extract_topic_performance

    # Compute deterministic topic metrics
    metrics = extract_topic_performance(quiz_results, mock_evaluation)

    prompt = weak_spot_analyzer_prompt(quiz_results, student_name)
    analysis = call_gemini_json(prompt, temperature=0.3)
    if isinstance(analysis, dict):
        analysis["topic_metrics"] = metrics
    return analysis


@server.tool(
    name="reschedule_spaced_revisions",
    description="Surgically generates priority-based spaced revisions (R1: 1-2 days, R2: 4-6 days) for weak topics, preserving completed sessions and student availability.",
)
def reschedule_spaced_revisions(
    current_schedule: dict,
    weak_topics: list,
    student_profile: dict,
) -> Dict[str, Any]:
    """MCP Tool: Priority-based spaced revision scheduler."""
    from core.weak_topic_manager import schedule_spaced_revisions
    return schedule_spaced_revisions(current_schedule, weak_topics, student_profile)


@server.tool(
    name="apply_schedule_changes",
    description="Applies surgical reschedule changes (add, move, remove) to daily schedule blocks.",
)
def apply_schedule_changes(schedule: dict, changes: list) -> dict:
    """MCP Tool: Merges schedule adjustment operations deterministically."""
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

    daily.sort(key=lambda d: d.get("date", ""))
    updated["daily_blocks"] = daily
    return updated


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SYLLABUS PDF PARSING & DOCUMENT ANALYSIS MCP TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@server.tool(
    name="analyze_pdf_quality",
    description="Inspects PDF page density, character volume, tables count, image ratio, and scanned status to select the optimal parsing tier.",
)
def analyze_pdf_quality(file_path: str) -> Dict[str, Any]:
    """MCP Tool: Evaluates document complexity and recommends the parsing tier."""
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    doc = fitz.open(str(p))
    num_pages = len(doc)
    total_chars = 0
    total_images = 0
    total_tables = 0
    has_electives = False

    for page_idx in range(min(num_pages, 20)):
        page = doc[page_idx]
        txt = page.get_text() or ""
        total_chars += len(txt)
        total_images += len(page.get_images())
        tabs = page.find_tables().tables
        total_tables += len(tabs)
        if re.search(r"\b(elective|open\s+elective|program\s+elective)\b", txt, re.IGNORECASE):
            has_electives = True

    avg_chars_per_page = total_chars / max(1, min(num_pages, 20))
    is_scanned = avg_chars_per_page < 40 and total_images > 0
    doc.close()

    # Determine recommended tier
    if is_scanned:
        recommended_tier = "ocr"
        tier_reason = "Document contains little selectable text; scanned or rasterized pages detected."
    elif total_tables > 0 or has_electives:
        recommended_tier = "structured"
        tier_reason = f"Document contains structured tables ({total_tables} detected) and/or elective curriculum choices."
    else:
        recommended_tier = "fast_text"
        tier_reason = "Standard clean text document; fast PyMuPDF extraction is optimal."

    return {
        "file_path": str(p),
        "num_pages": num_pages,
        "total_chars_sample": total_chars,
        "avg_chars_per_page": round(avg_chars_per_page, 1),
        "total_images": total_images,
        "total_tables": total_tables,
        "has_electives": has_electives,
        "is_scanned": is_scanned,
        "recommended_tier": recommended_tier,
        "tier_reason": tier_reason,
    }


@server.tool(
    name="extract_pdf_fast",
    description="Ultra-fast text extraction from a PDF syllabus using PyMuPDF (<0.1s).",
)
def extract_pdf_fast(file_path: str, max_pages: int = 50) -> Dict[str, Any]:
    """MCP Tool: Rapid PyMuPDF stream extraction."""
    from core.syllabus_parser import extract_text_from_pdf, clean_extracted_text, filter_administrative_fluff

    t0 = time.time()
    raw_text, meta = extract_text_from_pdf(file_path, max_pages=max_pages, ocr_fallback=False)
    elapsed = time.time() - t0

    return {
        "text": raw_text,
        "metadata": meta,
        "execution_time_seconds": round(elapsed, 4),
        "method": "PyMuPDF Fast Stream",
    }


@server.tool(
    name="extract_pdf_structured",
    description="Extracts structured Markdown with preserved tables and layout hierarchies using pymupdf4llm & PyMuPDF table detection.",
)
def extract_pdf_structured(file_path: str, max_pages: int = 50) -> Dict[str, Any]:
    """MCP Tool: Structured document extraction preserving tables and course grids."""
    from core.syllabus_parser import clean_extracted_text, filter_administrative_fluff

    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    t0 = time.time()
    doc = fitz.open(str(p))
    total_pages = len(doc)
    pages_to_process = min(total_pages, max_pages)

    # 1. Use pymupdf4llm for high-fidelity markdown with tables
    if pymupdf4llm is not None:
        md_text = pymupdf4llm.to_markdown(str(p), pages=list(range(pages_to_process)))
    else:
        # Fallback: extract text page by page with table representations
        chunks = []
        for pno in range(pages_to_process):
            page = doc[pno]
            chunks.append(page.get_text())
        md_text = "\n\n".join(chunks)

    doc.close()

    cleaned = clean_extracted_text(md_text)
    filtered = filter_administrative_fluff(cleaned)
    elapsed = time.time() - t0

    return {
        "text": filtered,
        "raw_char_count": len(md_text),
        "filtered_char_count": len(filtered),
        "pages_processed": pages_to_process,
        "total_pages": total_pages,
        "execution_time_seconds": round(elapsed, 4),
        "method": "PyMuPDF4LLM Structured Table Engine",
    }


@server.tool(
    name="extract_pdf_ocr",
    description="Performs OCR extraction for scanned or image-based PDF syllabi.",
)
def extract_pdf_ocr(file_path: str, max_pages: int = 10) -> Dict[str, Any]:
    """MCP Tool: OCR fallback for scanned syllabus documents."""
    from core.syllabus_parser import _extract_via_gemini_multimodal, clean_extracted_text, filter_administrative_fluff

    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    t0 = time.time()
    with open(p, "rb") as f:
        pdf_bytes = f.read()

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    ocr_raw = _extract_via_gemini_multimodal(pdf_bytes, doc=doc)
    doc.close()

    cleaned = clean_extracted_text(ocr_raw)
    filtered = filter_administrative_fluff(cleaned)
    elapsed = time.time() - t0

    return {
        "text": filtered,
        "char_count": len(filtered),
        "execution_time_seconds": round(elapsed, 4),
        "method": "Gemini Multimodal OCR",
    }


@server.tool(
    name="parse_syllabus_structure",
    description="Invokes Gemini via MCP to parse curriculum text into subject, modules, topics, subtopics, and electives while excluding reference books.",
)
def parse_syllabus_structure(
    extracted_text: str,
    subject_hint: str = "",
) -> Dict[str, Any]:
    """MCP Tool: Cognitive parsing of syllabus hierarchy with elective identification and textbook filtering."""
    from gemini_client import call_gemini_json
    from core.syllabus_parser import clean_extracted_text, filter_administrative_fluff, filter_reference_books

    t0 = time.time()
    cleaned = filter_reference_books(filter_administrative_fluff(clean_extracted_text(extracted_text)))

    prompt = f"""You are StudyMind AI, an expert academic curriculum analyst.
Analyze the following academic syllabus text and extract a structured hierarchy.

═══════════════════════════════════════════════════════
                   CRITICAL RULES
═══════════════════════════════════════════════════════
1. CORRECT SUBJECT IDENTIFICATION:
   - Identify the exact academic subject, degree, and semester/exam (e.g. "Computer Networks", "GATE 2027 Computer Science", "B.Tech CSE - 7th Semester").
2. MODULE & TOPIC HIERARCHY:
   - Extract major Units, Modules, or Sections into topics.
   - For each topic, provide concise title (<8 words), Bloom's difficulty (1-5), priority (1-5), and estimated study hours.
   - Extract key subtopics with key concepts.
3. ELECTIVES AS OPTIONAL ALTERNATIVES:
   - If the syllabus contains elective subjects or tracks (e.g. "Program Elective", "Open Elective", "Elective-I"), flag them explicitly:
     "is_elective": true,
     "elective_group": "Program Elective-4" (or whichever group it belongs to).
   - Core compulsory subjects should have "is_elective": false.
4. EXCLUDE REFERENCE BOOKS & TEXTBOOKS:
   - NEVER include textbooks, author names, publication editions, or reference book titles as topics.
5. NO DUPLICATE OR EMPTY TOPICS:
   - Ensure clean, unique units without duplicate entries.

Output ONLY a JSON object strictly adhering to this schema:
{{
  "subject": "Full Subject Name & Degree/Exam",
  "exam_type": "semester" or "competitive" or "certification",
  "has_electives": true or false,
  "topics": [
    {{
      "id": "t1",
      "title": "Unit / Module Name",
      "difficulty": 3,
      "priority": 4,
      "estimated_hours": 6.0,
      "is_elective": false,
      "elective_group": null,
      "prerequisites": [],
      "subtopics": [
        {{
          "id": "t1_s1",
          "title": "Subtopic Title",
          "estimated_hours": 3.0,
          "key_concepts": ["concept1", "concept2"]
        }}
      ]
    }}
  ]
}}

SYLLABUS CONTENT:
{cleaned[:8000]}
"""

    result = call_gemini_json(prompt, temperature=0.1, max_tokens=8192)
    elapsed = time.time() - t0

    # Post-validation and normalization
    topics = result.get("topics", [])
    total_hours = 0
    normalized_topics = []

    for i, t in enumerate(topics):
        tid = t.get("id") or f"t{i+1}"
        title = t.get("title", f"Unit {i+1}")
        difficulty = int(t.get("difficulty", 3))
        priority = int(t.get("priority", 3))
        hours = float(t.get("estimated_hours", 4.0))
        is_elective = bool(t.get("is_elective", False))
        elective_group = t.get("elective_group")

        total_hours += hours
        normalized_topics.append({
            "id": tid,
            "title": title,
            "difficulty": max(1, min(difficulty, 5)),
            "priority": max(1, min(priority, 5)),
            "estimated_hours": round(hours, 1),
            "is_elective": is_elective,
            "elective_group": elective_group,
            "prerequisites": t.get("prerequisites", []),
            "subtopics": t.get("subtopics", []),
        })

    result["topics"] = normalized_topics
    result["total_estimated_hours"] = round(total_hours, 1)
    result["exam_type"] = result.get("exam_type", "semester")
    result["has_electives"] = result.get("has_electives", any(t["is_elective"] for t in normalized_topics))
    result["execution_time_seconds"] = round(elapsed, 4)

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 3. STANDALONE SERVER EXECUTION (STDIO)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # When run via command line, run standard MCP server over stdio
    print("Starting StudyMind AI MCP Server over stdio...", file=sys.stderr)
    asyncio.run(server.run_stdio_async())
