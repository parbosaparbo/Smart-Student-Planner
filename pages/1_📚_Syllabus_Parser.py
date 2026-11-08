"""
StudyMind AI — Page 1: Syllabus Parser (MCP-Integrated)
Intelligent Multi-Tier Document Parsing Pipeline powered by Model Context Protocol (MCP)
"""
import streamlit as st
import json
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.syllabus_parser import (
    extract_text_from_pdf,
    clean_extracted_text,
    filter_administrative_fluff,
    filter_reference_books,
    parse_syllabus_fast,
    parse_syllabus_multi_tier,
    compute_pdf_sha256,
)
from storage import save_persistent_state
from ui_components import render_sidebar_header
from config import COLORS, DIFFICULTY_LABELS

st.set_page_config(
    page_title="Syllabus Parser — StudyMind AI",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)
render_sidebar_header()

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style='background:linear-gradient(135deg,{COLORS["primary"]}22,{COLORS["card_bg"]});
            border-left:4px solid {COLORS["primary"]};
            padding:1.4rem 2rem; border-radius:12px; margin-bottom:1.5rem;'>
  <div style='display:flex; justify-content:space-between; align-items:center;'>
    <div>
      <h1 style='margin:0; color:{COLORS["primary"]}; font-size:2rem;'>📚 Syllabus Parser</h1>
      <p style='margin:0.3rem 0 0; color:{COLORS["text_muted"]}; font-size:0.95rem;'>
        Intelligent Multi-Tier PDF parser powered by <strong>Model Context Protocol (MCP)</strong> with SHA-256 caching.
      </p>
    </div>
    <span style='background:{COLORS["card_bg"]}; border:1px solid {COLORS["primary"]}; padding:4px 12px; border-radius:20px; font-size:0.8rem; color:{COLORS["primary"]};'>
      ⚡ MCP Tool Calling Active
    </span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Input ──────────────────────────────────────────────────────────────────────
col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("Upload Syllabus")
    input_method = st.radio("Choose input method", ["📄 Upload PDF", "✏️ Paste Text"], horizontal=True)

    raw_text = ""
    uploaded_pdf = None

    if input_method == "📄 Upload PDF":
        uploaded_pdf = st.file_uploader("Upload your syllabus PDF", type=["pdf"], key="syllabus_pdf_uploader")
        if uploaded_pdf:
            sha256_hash, _ = compute_pdf_sha256(uploaded_pdf)
            st.caption(f"🔒 Document Fingerprint (SHA-256): `{sha256_hash[:20]}...`")

            # Extract preview text
            preview_cache_key = f"pdf_preview_{sha256_hash}"
            if preview_cache_key in st.session_state:
                raw_text, meta = st.session_state[preview_cache_key]
            else:
                with st.spinner("⚡ Extracting text preview with PyMuPDF..."):
                    try:
                        raw_text, meta = extract_text_from_pdf(uploaded_pdf, ocr_fallback=True)
                        st.session_state[preview_cache_key] = (raw_text, meta)
                    except Exception as ex:
                        st.error(f"❌ PDF extraction failed: {ex}")
                        raw_text, meta = "", {}

            if raw_text and meta:
                st.success(f"⚡ Extracted {meta.get('char_count', len(raw_text)):,} characters from {meta.get('num_pages', 1)} page(s) via **{meta.get('method', 'PyMuPDF')}**")
                with st.expander("👁️ Preview Extracted Clean Text", expanded=False):
                    st.text_area("Extracted Content", value=raw_text, height=200, disabled=True)
    else:
        sample_val = st.session_state.get("pasted_sample", "")
        raw_text = st.text_area(
            "Paste syllabus text here",
            value=sample_val,
            height=280,
            placeholder="Paste your syllabus content here...\n\nUnit 1: Data Structures\n  - Arrays, Linked Lists\n  - Trees and Graphs\n..."
        )
        if raw_text.strip():
            raw_text = clean_extracted_text(raw_text)

    parse_btn = st.button(
        "🔍 Parse Syllabus via MCP",
        type="primary",
        disabled=not (uploaded_pdf or raw_text.strip()),
        width="stretch",
    )

with col2:
    st.subheader("Multi-Tier MCP Pipeline")
    st.markdown("""
    StudyMind AI selects the optimal extraction tier dynamically:
    
    1. **🔒 Tier 0 — SHA-256 Cache:** Instant retrieval (<0.01s) for previously processed documents.
    2. **⚡ Tier 1 — PyMuPDF Fast Stream:** High-velocity C-engine extraction (<0.1s) for standard text.
    3. **📊 Tier 2 — Structured Table Extraction:** Uses `pymupdf4llm` & table detection to preserve course grids, elective options, and credit tables.
    4. **🔍 Tier 3 — Multimodal OCR:** Automatic OCR engine for scanned, photocopied, or image-heavy syllabi.
    5. **🤖 Cognitive Structuring:** Gemini extracts modules, units, Bloom's difficulty, and filters out reference books & administrative fluff.
    """)

# ── Parse Execution ────────────────────────────────────────────────────────────
if parse_btn:
    with st.spinner("⚡ Processing syllabus through MCP multi-tier pipeline..."):
        try:
            t0 = time.time()
            if uploaded_pdf is not None:
                result = parse_syllabus_multi_tier(uploaded_pdf)
            else:
                result = parse_syllabus_fast(raw_text)

            elapsed = round(time.time() - t0, 3)

            # Session State Caching & Persistence
            st.session_state["parsed_syllabus"] = result
            st.session_state["topic_tree"]      = result
            st.session_state["subject"]         = result.get("subject", "")
            save_persistent_state(st.session_state)

            cache_note = " (Instant SHA-256 Cache Hit!)" if result.get("cache_hit") else ""
            st.success(f"✅ Syllabus parsed in {result.get('execution_time_seconds', elapsed)}s via **{result.get('tier_used', 'MCP Tool')}**{cache_note}")

        except Exception as e:
            st.error(f"❌ Parsing failed: {e}")
            st.stop()

# ── Display Result ─────────────────────────────────────────────────────────────
active_syllabus = st.session_state.get("parsed_syllabus") or st.session_state.get("topic_tree")
if active_syllabus:
    result = active_syllabus
    topics = result.get("topics", [])
    total_hours = result.get("total_estimated_hours", 0)
    has_electives = result.get("has_electives", any(t.get("is_elective") for t in topics))

    # Summary metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Subject", result.get("subject", "—"))
    m2.metric("Total Topics", len(topics))
    m3.metric("Est. Hours", f"{total_hours}h")
    m4.metric("Exam Type", result.get("exam_type", "—").title())

    if result.get("tier_used"):
        st.info(f"🛠️ **MCP Pipeline Execution Audit:** Processed via `{result.get('tier_used')}` in `{result.get('execution_time_seconds', 0)}s` | Cache: `{ 'HIT' if result.get('cache_hit') else 'FRESH' }`")

    st.divider()

    # ── Elective Tracks vs Core Modules Handling ──────────────────────────────
    if has_electives:
        elective_groups = {}
        core_topics = []
        for t in topics:
            if t.get("is_elective"):
                group_name = t.get("elective_group") or "General Electives"
                elective_groups.setdefault(group_name, []).append(t)
            else:
                core_topics.append(t)

        st.subheader("🎯 Elective Tracks (Optional Alternatives)")
        st.caption("This syllabus contains elective tracks. Review each track and select your chosen subjects:")

        selected_topics = list(core_topics)

        # Tabbed display for elective groups
        if elective_groups:
            group_tabs = st.tabs(list(elective_groups.keys()))
            for tab_idx, (group_name, group_topics) in enumerate(elective_groups.items()):
                with group_tabs[tab_idx]:
                    st.markdown(f"**Choose an option for {group_name}:**")
                    topic_titles = [f"{t.get('title')} ({t.get('estimated_hours',0)}h)" for t in group_topics]
                    selected_idx = st.radio(
                        f"Select your subject for {group_name}:",
                        range(len(group_topics)),
                        format_func=lambda i: topic_titles[i],
                        key=f"elective_radio_{tab_idx}",
                    )
                    chosen_elective = group_topics[selected_idx]
                    selected_topics.append(chosen_elective)
                    st.info(f"📌 Active selection for **{group_name}**: **{chosen_elective.get('title')}**")

        # Update active topic tree if student selects specific electives
        if st.button("💾 Apply Elective Selections to Study Plan", key="btn_apply_electives"):
            updated_tree = dict(result)
            updated_tree["topics"] = selected_topics
            updated_tree["total_estimated_hours"] = round(sum(t.get("estimated_hours", 0) for t in selected_topics), 1)
            st.session_state["topic_tree"] = updated_tree
            st.session_state["parsed_syllabus"] = updated_tree
            save_persistent_state(st.session_state)
            st.success("✅ Study plan updated with your selected elective subjects!")

        st.divider()

    st.subheader("📋 Structured Topic Tree")

    # Topic cards
    for i, topic in enumerate(topics):
        difficulty = topic.get("difficulty", 1)
        priority   = topic.get("priority", 1)
        is_elective = topic.get("is_elective", False)
        elective_badge = f" [Optional Elective: {topic.get('elective_group')}]" if is_elective else ""

        diff_label = DIFFICULTY_LABELS.get(difficulty, "Unknown")
        diff_color = [COLORS["success"], COLORS["info"], COLORS["warning"], COLORS["warning"], COLORS["danger"]][max(0, min(difficulty - 1, 4))]

        with st.expander(
            f"**{topic.get('id','').upper()}** · {topic.get('title','Untitled')}{elective_badge} "
            f"| {topic.get('estimated_hours',0)}h | Priority {priority}/5",
            expanded=(i < 3)
        ):
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"**Difficulty:** :{diff_color}[{diff_label} ({difficulty}/5)]")
            c2.markdown(f"**Priority:** {'⭐' * priority}")
            c3.markdown(f"**Type:** {'🔹 Elective Alternative' if is_elective else '📌 Core Compulsory'}")

            subtopics = topic.get("subtopics", [])
            if subtopics:
                st.markdown("**Subtopics:**")
                for sub in subtopics:
                    concepts = ", ".join(sub.get("key_concepts", []))
                    st.markdown(
                        f"- **{sub.get('title','')}** ({sub.get('estimated_hours',0)}h)"
                        + (f" — *{concepts}*" if concepts else "")
                    )

    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        st.download_button(
            "⬇️ Download Topic Tree (JSON)",
            data=json.dumps(result, indent=2),
            file_name=f"{result.get('subject','syllabus').replace(' ','_')}_topic_tree.json",
            mime="application/json",
            width="stretch",
        )
    with col_b:
        if st.button("➡️ Go to Schedule Generator", width="stretch"):
            st.switch_page("pages/2_📅_Schedule_Generator.py")
