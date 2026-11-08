"""
StudyMind AI — Enhanced Multi-Tier Syllabus Parser & Document Analysis Engine
Integrated with the Model Context Protocol (MCP):
1. SHA-256 Document Caching for sub-0.01s repeat retrieval
2. Deterministic Quality Auditing & Intelligent Tool Selection:
   - Tier 1: PyMuPDF Fast Stream (<0.1s)
   - Tier 2: OpenDataLoader / PyMuPDF4LLM Table & Layout Structuring
   - Tier 3: Scanned OCR Fallback
3. Preprocessing Filters: Administrative Fluff & Reference Books Stripper
4. Cognitive Syllabus Understanding via MCP:
   - Accurate Subject Identification
   - Module & Unit Hierarchy
   - Elective Identification (represented as optional alternatives)
   - Reference books excluded from topics
"""
import hashlib
import io
import json
import os
import re
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

CACHE_FILE = Path(__file__).parent.parent / "data" / "syllabus_cache.json"

# Keywords identifying core academic syllabus content
SYLLABUS_KEYWORDS = re.compile(
    r"\b(unit|module|chapter|topics?|syllabus|course content|learning objectives|curriculum|section)\b",
    re.IGNORECASE,
)

# Administrative fluff patterns to strip before calling Gemini
ADMIN_FLUFF_PATTERNS = [
    re.compile(r"(?i)\b(?:attendance\s+policy|attendance\s+criteria|minimum\s+75%|attendance\s+requirement).*"),
    re.compile(r"(?i)\b(?:grading\s+rubric|grading\s+policy|marks\s+breakdown|evaluation\s+scheme|internal\s+assessment|mid\s+term\s+exam|end\s+semester\s+exam).*"),
    re.compile(r"(?i)\b(?:faculty\s+name|instructor|professor|office\s+hours|cabin\s+no|email\s*:|phone\s*:).*"),
    re.compile(r"(?i)\b(?:course\s+outcomes?|program\s+outcomes?|po1|po2|co1|co2|bloom'?s\s+taxonomy\s+level|mapping\s+matrix).*"),
    re.compile(r"(?i)\b(?:affiliated\s+to|approved\s+by\s+aicte|accredited\s+by\s+naac|iso\s+9001|college\s+of\s+engineering|university).*"),
    re.compile(r"(?i)\b(?:academic\s+integrity|plagiarism\s+policy|code\s+of\s+conduct|disciplinary\s+action).*"),
]

# Patterns for textbooks and reference reading lists
REFERENCE_BOOK_PATTERNS = [
    re.compile(r"(?i)^\s*(?:text\s*books?|reference\s*books?|books\s+recommended|suggested\s+readings?|recommended\s+books?|references?)\s*[:/]?"),
    re.compile(r"(?i)^\s*\d+[\.\)]\s*(?:[A-Z][a-z]+,?\s+)+.*(?:publisher|edition|tmh|pearson|wiley|mcgraw|oxford|cambridge|prentice|isbn|\d{4})"),
]


def ensure_cache_file():
    """Ensure syllabus cache directory and file exist."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({}, f)
        except Exception:
            pass


def compute_pdf_sha256(pdf_source: Union[str, Path, bytes, Any]) -> Tuple[str, bytes]:
    """Computes SHA-256 hash of the PDF source and returns (hash_hex, raw_bytes)."""
    if isinstance(pdf_source, (str, Path)):
        p = Path(pdf_source)
        with open(p, "rb") as f:
            raw_bytes = f.read()
    elif isinstance(pdf_source, bytes):
        raw_bytes = pdf_source
    elif hasattr(pdf_source, "read"):
        if hasattr(pdf_source, "seek"):
            pdf_source.seek(0)
        raw_bytes = pdf_source.read()
        if hasattr(pdf_source, "seek"):
            pdf_source.seek(0)
    else:
        raise TypeError(f"Unsupported pdf_source type: {type(pdf_source)}")

    sha256_hash = hashlib.sha256(raw_bytes).hexdigest()
    return sha256_hash, raw_bytes


def get_cached_parsed_syllabus(sha256_hash: str) -> Optional[Dict[str, Any]]:
    """Retrieves cached parsed syllabus by SHA-256 hash."""
    ensure_cache_file()
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get(sha256_hash)
    except Exception:
        pass
    return None


def save_cached_parsed_syllabus(sha256_hash: str, parsed_result: Dict[str, Any]):
    """Persists parsed syllabus result mapped to its SHA-256 hash."""
    ensure_cache_file()
    try:
        data = {}
        if CACHE_FILE.exists():
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        data[sha256_hash] = parsed_result
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        print(f"Warning: could not save syllabus cache: {e}")


def clean_extracted_text(text: str) -> str:
    """
    Cleans and normalizes raw text extracted from PDF:
    - Removes non-printable control characters & null bytes
    - Fixes broken hyphenations across line breaks
    - Collapses excessive horizontal whitespace and tabs
    - Condenses multiple consecutive blank lines into double newlines
    """
    if not text:
        return ""

    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(\b[A-Za-z]+)-\n([A-Za-z]+\b)", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text)

    lines = [line.strip() for line in text.split("\n")]
    cleaned_lines = []
    blank_count = 0
    for line in lines:
        if not line:
            blank_count += 1
            if blank_count <= 2:
                cleaned_lines.append("")
        else:
            blank_count = 0
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def filter_administrative_fluff(text: str) -> str:
    """
    Filters out administrative fluff (grading rubrics, attendance policies,
    faculty contact, accreditation headers, course outcomes).
    """
    if not text:
        return ""

    lines = text.split("\n")
    retained_lines: List[str] = []

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            retained_lines.append("")
            continue

        is_fluff = any(pattern.search(line_clean) for pattern in ADMIN_FLUFF_PATTERNS)
        if not is_fluff:
            retained_lines.append(line)

    filtered = "\n".join(retained_lines)
    filtered = re.sub(r"\n{3,}", "\n\n", filtered).strip()
    return filtered


def filter_reference_books(text: str) -> str:
    """
    Strips out Textbooks and Reference Books sections so that publication titles
    and author names are never mistakenly parsed as syllabus units.
    """
    if not text:
        return ""

    lines = text.split("\n")
    retained_lines: List[str] = []
    in_ref_block = False

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            retained_lines.append("")
            continue

        # Check if reference section starts
        if any(p.search(line_clean) for p in REFERENCE_BOOK_PATTERNS):
            in_ref_block = True
            continue

        # Check if a new academic unit / module / course starts, exiting the reference block
        if in_ref_block and (
            re.match(r"(?i)^(?:module|unit|chapter|section|course\s+code|course\s+title)\b", line_clean)
            or re.match(r"(?i)^[A-Z0-9]{6,}\b", line_clean)
        ):
            in_ref_block = False

        if not in_ref_block:
            retained_lines.append(line)

    filtered = "\n".join(retained_lines)
    filtered = re.sub(r"\n{3,}", "\n\n", filtered).strip()
    return filtered


def _extract_via_gemini_multimodal(pdf_bytes: bytes, doc=None) -> str:
    """Fallback OCR engine using Gemini Multimodal when PDF is scanned or image-based."""
    from gemini_client import _init_model

    ocr_prompt = (
        "Extract only the core academic Units and major Topics from this scanned syllabus document.\n"
        "Ignore rules, college info, and grading policies.\n"
        "Output the clean text of unit titles, chapters, and topics verbatim."
    )

    model = _init_model(temperature=0.1, max_tokens=2048)

    try:
        pdf_part = {"mime_type": "application/pdf", "data": pdf_bytes}
        response = model.generate_content([pdf_part, ocr_prompt])
        if response and response.text and len(response.text.strip()) > 30:
            return response.text.strip()
    except Exception:
        pass

    if doc is not None and len(doc) > 0:
        image_parts = []
        pages_to_render = min(len(doc), 6)
        for page_idx in range(pages_to_render):
            page = doc[page_idx]
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("jpeg")
            image_parts.append({"mime_type": "image/jpeg", "data": img_bytes})

        if image_parts:
            response = model.generate_content(image_parts + [ocr_prompt])
            if response and response.text:
                return response.text.strip()

    raise ValueError("Gemini Multimodal OCR was unable to extract legible text from this scanned PDF.")


def extract_text_from_pdf(
    pdf_source: Union[str, Path, bytes, Any],
    max_pages: int = 50,
    ocr_fallback: bool = True,
) -> Tuple[str, Dict[str, Any]]:
    """
    Sub-second PDF syllabus text extraction using PyMuPDF (fitz) with keyword page filtering.
    Preserved for backward compatibility.
    """
    if fitz is None:
        raise ImportError("PyMuPDF (`fitz`) is not installed. Please install via `pip install pymupdf`.")

    sha256_hash, pdf_bytes = compute_pdf_sha256(pdf_source)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    total_pages = len(doc)
    if total_pages == 0:
        doc.close()
        raise ValueError("The provided PDF file contains 0 pages.")

    pages_to_read = min(total_pages, max_pages)

    extracted_pages: List[str] = []
    if total_pages > 5:
        matched_pages = []
        for p_idx in range(pages_to_read):
            page_txt = doc[p_idx].get_text() or ""
            if SYLLABUS_KEYWORDS.search(page_txt):
                matched_pages.append(page_txt)

        if len(matched_pages) >= 2:
            extracted_pages = matched_pages
        else:
            extracted_pages = [doc[i].get_text() for i in range(min(5, total_pages))]
    else:
        extracted_pages = [p.get_text() for p in doc[:pages_to_read]]

    raw_combined = "".join(extracted_pages)
    cleaned = clean_extracted_text(raw_combined)
    filtered = filter_reference_books(filter_administrative_fluff(cleaned))

    metadata: Dict[str, Any] = {
        "num_pages": total_pages,
        "pages_processed": len(extracted_pages),
        "char_count": len(filtered),
        "word_count": len(filtered.split()),
        "method": "PyMuPDF Fast Engine",
        "is_scanned": False,
        "sha256": sha256_hash,
    }

    if len(filtered.strip()) < 50:
        if ocr_fallback:
            try:
                ocr_text = _extract_via_gemini_multimodal(pdf_bytes, doc=doc)
                cleaned_ocr = clean_extracted_text(ocr_text)
                filtered_ocr = filter_reference_books(filter_administrative_fluff(cleaned_ocr))
                if len(filtered_ocr.strip()) >= 50:
                    filtered = filtered_ocr
                    metadata["char_count"] = len(filtered)
                    metadata["word_count"] = len(filtered.split())
                    metadata["method"] = "Gemini Multimodal OCR Fallback"
                    metadata["is_scanned"] = True
            except Exception as ocr_err:
                print(f"Gemini OCR fallback error: {ocr_err}")
        else:
            metadata["is_scanned"] = True

    doc.close()
    return filtered, metadata


def parse_syllabus_multi_tier(
    pdf_source: Union[str, Path, bytes, Any],
    max_pages: int = 50,
) -> Dict[str, Any]:
    """
    Intelligent Multi-Tier MCP Syllabus Parsing Pipeline:
    1. SHA-256 Hash Check: Sub-0.01s cache return on duplicate files.
    2. MCP Tier Selection:
       - Tier 1: Fast PyMuPDF stream
       - Tier 2: OpenDataLoader / PyMuPDF4LLM Structured Table Extraction
       - Tier 3: OCR for scanned PDFs
    3. Deterministic Preprocessing (Fluff + Reference Books Removal)
    4. MCP Cognitive Structuring via Gemini (Modules, Topics, Subtopics, Elective identification)
    5. Validation, Execution-Time Auditing, and Output Normalization
    """
    from mcp_client import mcp_client

    t_start = time.time()
    sha256_hash, pdf_bytes = compute_pdf_sha256(pdf_source)

    # ── Step 0: Check SHA-256 Persistent Cache ────────────────────────────────
    cached = get_cached_parsed_syllabus(sha256_hash)
    if cached:
        cached["cache_hit"] = True
        cached["execution_time_seconds"] = round(time.time() - t_start, 4)
        return cached

    # Save to temp location for MCP tool consumption if needed
    temp_dir = Path(__file__).parent.parent / "data" / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_pdf_path = temp_dir / f"{sha256_hash[:16]}.pdf"
    if not temp_pdf_path.exists():
        with open(temp_pdf_path, "wb") as f:
            f.write(pdf_bytes)

    # ── Step 1: Quality & Complexity Audit via MCP ───────────────────────────
    doc_quality = mcp_client.call_tool("analyze_pdf_quality", {"file_path": str(temp_pdf_path)})
    recommended_tier = doc_quality.get("recommended_tier", "fast_text")

    # ── Step 2: Intelligent Tool Selection ────────────────────────────────────
    tier_used = "Tier 1: PyMuPDF Fast Stream"
    extracted_text = ""

    if recommended_tier == "ocr" or doc_quality.get("is_scanned"):
        tier_used = "Tier 3: Gemini Multimodal OCR"
        ocr_res = mcp_client.call_tool("extract_pdf_ocr", {"file_path": str(temp_pdf_path), "max_pages": 10})
        extracted_text = ocr_res.get("text", "")
    elif recommended_tier == "structured" or doc_quality.get("total_tables", 0) > 0 or doc_quality.get("has_electives"):
        tier_used = "Tier 2: PyMuPDF4LLM Structured Table Extraction"
        struct_res = mcp_client.call_tool("extract_pdf_structured", {"file_path": str(temp_pdf_path), "max_pages": max_pages})
        extracted_text = struct_res.get("text", "")
    else:
        tier_used = "Tier 1: PyMuPDF Fast Stream"
        fast_res = mcp_client.call_tool("extract_pdf_fast", {"file_path": str(temp_pdf_path), "max_pages": max_pages})
        extracted_text = fast_res.get("text", "")

    # Fallback if primary extraction yielded inadequate content
    if len(extracted_text.strip()) < 100 and tier_used != "Tier 3: Gemini Multimodal OCR":
        tier_used = "Tier 3: OCR Fallback"
        ocr_res = mcp_client.call_tool("extract_pdf_ocr", {"file_path": str(temp_pdf_path), "max_pages": 10})
        extracted_text = ocr_res.get("text", "")

    # ── Step 3: Deterministic Preprocessing ───────────────────────────────────
    cleaned_text = filter_reference_books(filter_administrative_fluff(clean_extracted_text(extracted_text)))

    # ── Step 4: Cognitive Syllabus Structuring via MCP ────────────────────────
    parsed_result = mcp_client.call_tool(
        "parse_syllabus_structure",
        {
            "extracted_text": cleaned_text,
            "subject_hint": "",
        }
    )

    # ── Step 5: Post-Processing & Validation ──────────────────────────────────
    total_elapsed = round(time.time() - t_start, 4)
    parsed_result["cache_hit"] = False
    parsed_result["sha256"] = sha256_hash
    parsed_result["tier_used"] = tier_used
    parsed_result["execution_time_seconds"] = total_elapsed
    parsed_result["document_metrics"] = {
        "num_pages": doc_quality.get("num_pages", 0),
        "total_tables": doc_quality.get("total_tables", 0),
        "has_electives": doc_quality.get("has_electives", False),
        "char_count": len(cleaned_text),
    }

    # Save to persistent SHA-256 cache
    save_cached_parsed_syllabus(sha256_hash, parsed_result)

    # Clean up temp file
    try:
        if temp_pdf_path.exists():
            temp_pdf_path.unlink()
    except Exception:
        pass

    return parsed_result


def parse_syllabus_fast(raw_text: str) -> Dict[str, Any]:
    """
    Cognitive syllabus parser for pasted text via MCP tool.
    Preserved for backward compatibility.
    """
    from mcp_client import mcp_client

    t0 = time.time()
    cleaned = filter_reference_books(filter_administrative_fluff(clean_extracted_text(raw_text)))
    result = mcp_client.call_tool("parse_syllabus_structure", {"extracted_text": cleaned})
    result["execution_time_seconds"] = round(time.time() - t0, 4)
    result["tier_used"] = "Pasted Text Clean Extraction"
    return result
