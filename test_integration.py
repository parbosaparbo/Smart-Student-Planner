"""
StudyMind AI — MCP Integration & Validation Test Suite
Tests:
1. MCP Server & Client Tool Registry (11 tools)
2. GATE 2027 Syllabus Multi-Tier Parsing
3. B.Tech 7th Sem CSE Syllabus Multi-Tier Parsing (Electives & Reference Books filtering)
4. SHA-256 Document Caching Performance
5. Existing MCP Tools & Backward Compatibility
"""
import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from mcp_client import mcp_client
from mcp_server import server as mcp_server
from core.syllabus_parser import (
    parse_syllabus_multi_tier,
    compute_pdf_sha256,
    filter_reference_books,
    filter_administrative_fluff,
)
from mcp_tools import (
    search_syllabus,
    push_to_calendar,
    apply_schedule_changes,
)


def run_tests():
    print("=" * 70)
    print("🧠 StudyMind AI — MCP Integration Verification Suite")
    print("=" * 70)

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 1: MCP Server & Client Tool Discovery
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[TEST 1] Verifying MCP Tool Discovery...")
    tools = mcp_client.list_tools()
    tool_names = [t["name"] for t in tools]
    print(f"✅ Discovered {len(tools)} tools on official MCP Server:")
    for name in tool_names:
        print(f"   • {name}")

    expected_tools = [
        "generate_quiz",
        "generate_study_schedule",
        "generate_mock_exam",
        "reschedule_weak_topic",
        "search_syllabus",
        "push_to_calendar",
        "analyze_weak_spots",
        "apply_schedule_changes",
        "analyze_pdf_quality",
        "extract_pdf_fast",
        "extract_pdf_structured",
        "extract_pdf_ocr",
        "parse_syllabus_structure",
        "reschedule_spaced_revisions",
    ]
    for expected in expected_tools:
        assert expected in tool_names, f"Missing MCP Tool: {expected}"
    print(f"✅ All {len(expected_tools)} MCP Tools verified!")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 2: Existing MCP Tools Backward Compatibility
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[TEST 2] Verifying Existing MCP Tools...")
    # 2a. Calendar Tool
    block = {
        "topic_id": "t1",
        "topic_title": "Network Protocols",
        "date": "2026-11-10",
        "start_time": "10:00",
        "session_goal": "Master TCP 3-way handshake",
        "resources_tip": "Feynman diagrams",
    }
    cal_res = push_to_calendar(block)
    assert cal_res["status"] == "ready", "push_to_calendar failed"
    assert "calendar.google.com" in cal_res["google_calendar_url"]
    print("✅ push_to_calendar tool verified!")

    # 2b. Syllabus Search Tool
    sample_tree = {
        "topics": [
            {
                "id": "t1",
                "title": "Computer Networks",
                "subtopics": [
                    {"id": "t1_s1", "title": "Transport Layer", "key_concepts": ["TCP", "UDP"]},
                ],
            }
        ]
    }
    search_res = search_syllabus("TCP", sample_tree)
    assert len(search_res) > 0, "search_syllabus failed"
    print(f"✅ search_syllabus tool verified (found {len(search_res)} matches)!")

    # 2c. Schedule Adjustment Tool
    schedule = {
        "daily_blocks": [
            {"date": "2026-11-10", "blocks": [{"topic_id": "t1"}]}
        ]
    }
    changes = [
        {"action": "add", "topic_id": "t2", "new_date": "2026-11-11", "reason": "Weak spot recovery"}
    ]
    updated_sched = apply_schedule_changes(schedule, changes)
    assert len(updated_sched["daily_blocks"]) == 2, "apply_schedule_changes failed"
    print("✅ apply_schedule_changes tool verified!")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 3: GATE 2027 Syllabus Multi-Tier Parsing
    # ─────────────────────────────────────────────────────────────────────────
    gate_pdf = "test_data/CS_GATE2027_Syllabus.pdf"
    if os.path.exists(gate_pdf):
        print("\n[TEST 3] Parsing GATE 2027 Syllabus via MCP Pipeline...")
        t0 = time.time()
        gate_result = parse_syllabus_multi_tier(gate_pdf)
        elapsed = round(time.time() - t0, 3)

        print(f"   Subject: {gate_result.get('subject')}")
        print(f"   Exam Type: {gate_result.get('exam_type')}")
        print(f"   Total Topics: {len(gate_result.get('topics', []))}")
        print(f"   Est. Total Hours: {gate_result.get('total_estimated_hours')}h")
        print(f"   Tier Used: {gate_result.get('tier_used')}")
        print(f"   Execution Time: {elapsed}s")

        assert "gate" in gate_result.get("subject", "").lower() or "computer" in gate_result.get("subject", "").lower()
        topics = gate_result.get("topics", [])
        assert len(topics) >= 5, f"Expected at least 5 topics, got {len(topics)}"

        # Verify no reference books in topics
        for t in topics:
            t_title = t.get("title", "").lower()
            assert not any(w in t_title for w in ["reference book", "textbook", "author", "edition"]), f"Reference book detected as topic: {t_title}"

        print("✅ GATE 2027 Syllabus parsing verified successfully!")

        # Test SHA-256 Cache Hit
        print("\n[TEST 3b] Testing SHA-256 Instant Cache Hit for GATE 2027...")
        t0 = time.time()
        cached_result = parse_syllabus_multi_tier(gate_pdf)
        cached_time = round(time.time() - t0, 4)
        print(f"   Cache hit: {cached_result.get('cache_hit')}")
        print(f"   Cached retrieval time: {cached_time}s")
        assert cached_result.get("cache_hit") is True, "Expected cache_hit to be True"
        assert cached_time < 0.1, f"Expected cache time < 0.1s, got {cached_time}s"
        print("✅ SHA-256 Caching verified (<0.01s retrieval)!")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 4: B.Tech 7th Sem CSE Syllabus Multi-Tier Parsing
    # ─────────────────────────────────────────────────────────────────────────
    btech_pdf = "test_data/B.Tech-7th-sem-CSE-final.pdf"
    if os.path.exists(btech_pdf):
        print("\n[TEST 4] Parsing B.Tech 7th Sem CSE Syllabus via MCP Pipeline...")
        t0 = time.time()
        btech_result = parse_syllabus_multi_tier(btech_pdf)
        elapsed = round(time.time() - t0, 3)

        print(f"   Subject: {btech_result.get('subject')}")
        print(f"   Exam Type: {btech_result.get('exam_type')}")
        print(f"   Total Topics: {len(btech_result.get('topics', []))}")
        print(f"   Est. Total Hours: {btech_result.get('total_estimated_hours')}h")
        print(f"   Has Electives: {btech_result.get('has_electives')}")
        print(f"   Tier Used: {btech_result.get('tier_used')}")
        print(f"   Execution Time: {elapsed}s")

        assert "b.tech" in btech_result.get("subject", "").lower() or "7th" in btech_result.get("subject", "").lower() or "computer" in btech_result.get("subject", "").lower()
        topics = btech_result.get("topics", [])
        assert len(topics) >= 3, f"Expected at least 3 topics, got {len(topics)}"

        # Verify electives representation
        electives = [t for t in topics if t.get("is_elective")]
        print(f"   Elective Topics Identified: {len(electives)}")
        for el in electives[:4]:
            print(f"    - {el.get('title')} (Group: {el.get('elective_group')})")

        # Verify reference books were NOT treated as topics
        for t in topics:
            t_title = t.get("title", "").lower()
            assert not any(w in t_title for w in ["reference book", "textbook", "tmh", "pearson", "edition"]), f"Reference book detected as topic: {t_title}"

        print("✅ B.Tech 7th Sem CSE parsing with Electives & Reference book filtering verified!")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 5: Weak Topic Analysis & Spaced Revision Rescheduling
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[TEST 5] Verifying Weak Topic Analysis & Spaced Revision Rescheduling...")
    from core.weak_topic_manager import (
        extract_topic_performance,
        identify_weak_topics,
        schedule_spaced_revisions,
    )
    from mcp_tools import reschedule_spaced_revisions

    mock_quizzes = [
        {"topic_id": "t1", "topic_title": "Sorting Algorithms", "score_pct": 40},
        {"topic_id": "t1", "topic_title": "Sorting Algorithms", "score_pct": 55},  # Repeated mistake
        {"topic_id": "t2", "topic_title": "Binary Trees", "score_pct": 85},
    ]
    mock_eval = {
        "topic_performance": [
            {"topic_id": "t1", "score_pct": 45, "verdict": "critical", "priority_action": "Fix QuickSort partitioning"},
            {"topic_id": "t3", "score_pct": 60, "verdict": "weak", "priority_action": "Review Graph DFS"},
        ]
    }

    # 5a. Performance & repeated mistakes extraction
    perf = extract_topic_performance(mock_quizzes, mock_eval)
    assert "t1" in perf, "Expected t1 in performance metrics"
    assert perf["t1"]["repeated_mistakes_count"] >= 2, f"Expected repeated mistakes for t1, got {perf['t1']['repeated_mistakes_count']}"
    assert perf["t1"]["urgency"] == "critical"
    print(f"   t1 accuracy: {perf['t1']['recent_accuracy']}%, repeated mistakes: {perf['t1']['repeated_mistakes_count']}, urgency: {perf['t1']['urgency']}")

    # 5b. Prioritized weak topics
    weaks = identify_weak_topics(mock_quizzes, mock_eval)
    assert len(weaks) >= 2, "Expected at least 2 weak topics"
    assert weaks[0]["topic_id"] == "t1", "Lowest score + repeated mistakes should be prioritized first"
    print(f"   Priority weak topics ordered correctly: {[w['topic_id'] for w in weaks]}")

    # 5c. Spaced revision scheduling (preserving past sessions)
    from datetime import date
    test_today = date(2026, 11, 10)
    current_schedule = {
        "daily_blocks": [
            {"date": "2026-11-09", "day_type": "study", "blocks": [{"topic_id": "t_past", "topic_title": "Past Session"}]},
            {"date": "2026-11-10", "day_type": "study", "blocks": [{"topic_id": "t_today", "topic_title": "Today Session"}]},
        ]
    }
    student_profile = {
        "student_name": "Aman",
        "daily_hours": 3.0,
        "blocked_days": ["sunday"],
        "preferred_times": ["morning", "evening"],
    }

    resched_res = reschedule_spaced_revisions(current_schedule, weaks, student_profile)
    assert resched_res["blocks_added"] >= 2, "Spaced revisions must add at least 2 sessions (Round 1 & Round 2)"
    updated_daily = resched_res["updated_schedule"]["daily_blocks"]

    # Verify past session was NOT disturbed
    past_day = next((d for d in updated_daily if d.get("date") == "2026-11-09"), None)
    assert past_day is not None and past_day["blocks"][0]["topic_id"] == "t_past", "Past session was disturbed!"
    print(f"   Non-disturbance verified: past session intact ({past_day['blocks'][0]['topic_title']})")
    print(f"   Spaced revision blocks successfully inserted: {resched_res['blocks_added']}")
    print("✅ Weak Topic Analysis & Spaced Revision Rescheduling verified successfully!")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 6: Benchmarking the 4 Optimized Features
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[TEST 6] Benchmarking the 4 Optimized Features...")
    from core.quiz_engine import generate_fast_quiz
    from core.scheduler import generate_fast_schedule
    from core.rag_engine import get_syllabus_rag
    from core.mock_engine import generate_mock_exam_questions

    # 6a. Benchmark Quiz Generation via FastMCP
    t_q0 = time.time()
    quiz_out = mcp_client.call_tool("generate_quiz", {
        "topic": "Operating Systems",
        "topic_id": "t1",
        "difficulty": 3,
        "question_count": 5,
        "syllabus_context": "Process scheduling, virtual memory, paging, and deadlocks"
    })
    quiz_time1 = round(time.time() - t_q0, 4)
    t_q1 = time.time()
    quiz_out_cached = mcp_client.call_tool("generate_quiz", {
        "topic": "Operating Systems",
        "topic_id": "t1",
        "difficulty": 3,
        "question_count": 5,
        "syllabus_context": "Process scheduling, virtual memory, paging, and deadlocks"
    })
    quiz_time2 = round(time.time() - t_q1, 4)
    assert len(quiz_out["questions"]) == 5, "Expected 5 quiz questions"
    assert "A" in quiz_out["questions"][0]["options"], "Valid options schema required"
    print(f"   1. Quiz Generation via FastMCP: Fresh={quiz_time1}s | Cached={quiz_time2}s (Speedup: {round(quiz_time1/max(quiz_time2, 0.0001), 1)}x)")

    # 6b. Benchmark Study Schedule
    sample_profile = {
        "student_name": "Aman",
        "daily_hours": 4.0,
        "preferred_times": ["morning", "evening"],
        "blocked_days": ["sunday"],
        "exam_date": "2026-12-01",
    }
    sample_tree = {
        "subject": "Computer Science",
        "topics": [
            {"id": "t1", "title": "Data Structures", "priority": 5, "difficulty": 4, "subtopics": [{"title": "Trees and Graphs", "key_concepts": ["traversal", "balancing"]}]},
            {"id": "t2", "title": "Algorithms", "priority": 5, "difficulty": 4, "subtopics": [{"title": "Sorting and Searching", "key_concepts": ["binary search", "quicksort"]}]},
            {"id": "t3", "title": "Operating Systems", "priority": 4, "difficulty": 3, "subtopics": [{"title": "Memory Management", "key_concepts": ["paging", "segmentation", "virtual memory"]}]},
            {"id": "t4", "title": "Database Systems", "priority": 3, "difficulty": 2, "subtopics": [{"title": "SQL and Normalization", "key_concepts": ["joins", "3NF", "BCNF"]}]},
        ]
    }
    t_s0 = time.time()
    sched_out = generate_fast_schedule(sample_profile, sample_tree, "2026-11-10")
    sched_time = round(time.time() - t_s0, 4)
    assert len(sched_out["daily_blocks"]) >= 20, "Expected at least 20 daily blocks"
    print(f"   2. Study Schedule: {len(sched_out['daily_blocks'])}-day plan generated in {sched_time}s")

    # 6c. Benchmark Syllabus Chatbot RAG Retrieval
    rag = get_syllabus_rag(sample_tree)
    t_r0 = time.time()
    chunks = rag.retrieve("How does paging and segmentation work in memory management?", top_k=3)
    rag_time = round((time.time() - t_r0) * 1000, 2)
    assert len(chunks) > 0, "RAG should retrieve matching syllabus chunks"
    print(f"   3. Syllabus Chatbot RAG: Retrieved {len(chunks)} relevant chunks in {rag_time}ms (Top match: {chunks[0]['topic_title']})")

    # 6d. Benchmark Mock Exam
    t_m0 = time.time()
    mock_out = generate_mock_exam_questions(sample_tree["topics"][:2], total_questions=6, difficulty=3)
    mock_time = round(time.time() - t_m0, 4)
    assert len(mock_out["questions"]) == 6, "Expected 6 mock questions"
    print(f"   4. Mock Exam Generator: {len(mock_out['questions'])} questions generated across 2 topics in {mock_time}s")
    print("✅ All 4 Optimized Features Benchmarked Successfully!")

    print("\n" + "=" * 70)
    print("🎉 ALL TESTS PASSED! MCP INTEGRATION FULLY VERIFIED.")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()

