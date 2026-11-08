"""
StudyMind AI — MCP Tools Module (Re-export & Bridge)
Maintains 100% backward compatibility for all Streamlit pages while exposing
the complete Model Context Protocol (MCP) tool registry.
"""
from mcp_server import (
    generate_quiz,
    reschedule_weak_topic,
    reschedule_spaced_revisions,
    search_syllabus,
    push_to_calendar,
    analyze_weak_spots,
    apply_schedule_changes,
    analyze_pdf_quality,
    extract_pdf_fast,
    extract_pdf_structured,
    extract_pdf_ocr,
    parse_syllabus_structure,
    server as mcp_server,
)
from mcp_client import mcp_client, MCPClient

__all__ = [
    "generate_quiz",
    "reschedule_weak_topic",
    "reschedule_spaced_revisions",
    "search_syllabus",
    "push_to_calendar",
    "analyze_weak_spots",
    "apply_schedule_changes",
    "analyze_pdf_quality",
    "extract_pdf_fast",
    "extract_pdf_structured",
    "extract_pdf_ocr",
    "parse_syllabus_structure",
    "mcp_server",
    "mcp_client",
    "MCPClient",
]
