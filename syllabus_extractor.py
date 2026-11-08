"""
StudyMind AI — Syllabus Extractor Convenience Re-export
"""
from core.syllabus_parser import (
    extract_text_from_pdf,
    clean_extracted_text,
    filter_administrative_fluff,
    filter_reference_books,
    parse_syllabus_fast,
    parse_syllabus_multi_tier,
    compute_pdf_sha256,
)

__all__ = [
    "extract_text_from_pdf",
    "clean_extracted_text",
    "filter_administrative_fluff",
    "filter_reference_books",
    "parse_syllabus_fast",
    "parse_syllabus_multi_tier",
    "compute_pdf_sha256",
]
