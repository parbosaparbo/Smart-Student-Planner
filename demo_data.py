"""
StudyMind AI — Sample / Demo Data Loader
Provides instant test data for Semester VII students to explore all features immediately.
"""
from datetime import date, timedelta
from typing import Dict, Any


def get_demo_state() -> Dict[str, Any]:
    """Return a complete populated state for testing."""
    today = date.today()
    exam = today + timedelta(days=21)

    student_profile = {
        "student_name": "Aarav",
        "subject": "Computer Networks & Distributed Systems (Sem VII)",
        "exam_date": str(exam),
        "daily_hours": 4.0,
        "preferred_times": ["morning", "evening"],
        "blocked_days": ["sunday"],
        "current_level": "intermediate",
        "known_topics": ["OSI Model", "HTTP Basics"],
        "learning_style": "visual",
    }

    topic_tree = {
        "subject": "Computer Networks & Distributed Systems",
        "total_estimated_hours": 36.0,
        "exam_type": "semester",
        "topics": [
            {
                "id": "t1",
                "title": "Physical & Data Link Layers",
                "difficulty": 2,
                "estimated_hours": 6.0,
                "priority": 4,
                "prerequisites": [],
                "subtopics": [
                    {"id": "t1_s1", "title": "Framing & Error Correction (CRC, Hamming)", "estimated_hours": 3.0, "key_concepts": ["CRC", "Hamming Code", "Checksum"]},
                    {"id": "t1_s2", "title": "Sliding Window & MAC (CSMA/CD)", "estimated_hours": 3.0, "key_concepts": ["Go-Back-N", "Selective Repeat", "CSMA/CD"]}
                ]
            },
            {
                "id": "t2",
                "title": "Network Layer & Routing Protocols",
                "difficulty": 4,
                "estimated_hours": 8.0,
                "priority": 5,
                "prerequisites": ["t1"],
                "subtopics": [
                    {"id": "t2_s1", "title": "IPv4 / IPv6 Subnetting & CIDR", "estimated_hours": 4.0, "key_concepts": ["Subnet Masks", "CIDR notation", "NAT"]},
                    {"id": "t2_s2", "title": "Dijkstra & Distance Vector Routing", "estimated_hours": 4.0, "key_concepts": ["Bellman-Ford", "Link State", "Count to Infinity"]}
                ]
            },
            {
                "id": "t3",
                "title": "Transport Layer (TCP/UDP & Congestion)",
                "difficulty": 4,
                "estimated_hours": 8.0,
                "priority": 5,
                "prerequisites": ["t2"],
                "subtopics": [
                    {"id": "t3_s1", "title": "TCP 3-Way Handshake & Flow Control", "estimated_hours": 4.0, "key_concepts": ["SYN-ACK", "Sliding Window", "FIN-ACK"]},
                    {"id": "t3_s2", "title": "TCP Congestion Control (Reno, Tahoe, CUBIC)", "estimated_hours": 4.0, "key_concepts": ["Slow Start", "Congestion Avoidance", "Fast Retransmit"]}
                ]
            },
            {
                "id": "t4",
                "title": "Application Layer & Socket Programming",
                "difficulty": 3,
                "estimated_hours": 6.0,
                "priority": 3,
                "prerequisites": ["t3"],
                "subtopics": [
                    {"id": "t4_s1", "title": "DNS Hierarchy & HTTP/2 vs HTTP/3", "estimated_hours": 3.0, "key_concepts": ["A/AAAA Records", "QUIC Protocol", "Multiplexing"]},
                    {"id": "t4_s2", "title": "Python TCP / UDP Sockets", "estimated_hours": 3.0, "key_concepts": ["socket.bind", "socket.listen", "multithreading"]}
                ]
            },
            {
                "id": "t5",
                "title": "Network Security & Cryptography",
                "difficulty": 5,
                "estimated_hours": 8.0,
                "priority": 5,
                "prerequisites": ["t3"],
                "subtopics": [
                    {"id": "t5_s1", "title": "RSA Encryption & Digital Signatures", "estimated_hours": 4.0, "key_concepts": ["Public Key", "Private Key", "SHA-256"]},
                    {"id": "t5_s2", "title": "TLS 1.3 Handshake & Modern Firewalls", "estimated_hours": 4.0, "key_concepts": ["Diffie-Hellman", "Certificates", "Stateful Inspection"]}
                ]
            }
        ]
    }

    # Daily blocks for the next 7 days
    daily_blocks = []
    for i in range(7):
        day_date = str(today + timedelta(days=i))
        if i == 6:
            # rest day
            daily_blocks.append({"date": day_date, "day_type": "rest", "blocks": []})
        elif i == 5:
            # mock test
            daily_blocks.append({
                "date": day_date,
                "day_type": "mock_test",
                "blocks": [
                    {
                        "topic_id": "t2",
                        "topic_title": "Network Layer & Subnetting",
                        "start_time": "09:00",
                        "duration_minutes": 90,
                        "session_goal": "Timed mock test on Subnetting and Dijkstra routing",
                        "resources_tip": "Work through 5 CIDR subnetting problems without looking at solutions first."
                    }
                ]
            })
        else:
            t = topic_tree["topics"][i % len(topic_tree["topics"])]
            daily_blocks.append({
                "date": day_date,
                "day_type": "study",
                "blocks": [
                    {
                        "topic_id": t["id"],
                        "topic_title": t["title"],
                        "start_time": "08:30",
                        "duration_minutes": 120,
                        "session_goal": f"Cover core concepts: {', '.join(t['subtopics'][0]['key_concepts'])}",
                        "resources_tip": "Active recall: Draw the packet flow diagram before looking at reference."
                    },
                    {
                        "topic_id": t["id"],
                        "topic_title": f"{t['title']} — Practice",
                        "start_time": "18:00",
                        "duration_minutes": 90,
                        "session_goal": f"Solve 3 scenario problems on {t['subtopics'][0]['title']}",
                        "resources_tip": "Feynman technique: Explain the protocol to a peer or rubber duck."
                    }
                ]
            })

    schedule = {
        "schedule_summary": {
            "total_study_hours": 26.5,
            "rest_days": [str(today + timedelta(days=6))],
            "mock_test_days": [str(today + timedelta(days=5))],
            "revision_start_date": str(today + timedelta(days=14))
        },
        "daily_blocks": daily_blocks
    }

    quiz_results = [
        {
            "topic_id": "t1",
            "topic_title": "Physical & Data Link Layers",
            "score_pct": 80,
            "correct": 4,
            "total": 5,
            "time_taken": 280,
            "answers": {"q1": "A", "q2": "B", "q3": "C", "q4": "A", "q5": "D"},
            "questions": [
                {"id": "q1", "question": "In a noisy channel using Go-Back-N, if frame 3 is lost...", "correct_answer": "A"},
                {"id": "q2", "question": "Why does Selective Repeat require window size <= 2^(m-1)?", "correct_answer": "B"}
            ]
        },
        {
            "topic_id": "t2",
            "topic_title": "Network Layer & Routing Protocols",
            "score_pct": 40,
            "correct": 2,
            "total": 5,
            "time_taken": 310,
            "answers": {"q1": "B", "q2": "C", "q3": "A", "q4": "C", "q5": "B"},
            "questions": [
                {"id": "q1", "question": "Given /27 CIDR block, calculate valid host addresses...", "correct_answer": "D"},
                {"id": "q2", "question": "Count-to-infinity problem in Bellman-Ford occurs when...", "correct_answer": "A"}
            ]
        }
    ]

    return {
        "student_profile": student_profile,
        "topic_tree": topic_tree,
        "subject": topic_tree["subject"],
        "schedule": schedule,
        "quiz_results": quiz_results,
    }

