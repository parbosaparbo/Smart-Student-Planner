"""
StudyMind AI — Page 8: Active Recall Flashcards
Spaced repetition & Feynman technique flashcards
"""
import streamlit as st
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from gemini_client import call_gemini_json
from prompts import flashcard_generator_prompt
from storage import save_persistent_state
from config import COLORS

st.set_page_config(page_title="Flashcards — StudyMind AI", page_icon="🃏", layout="wide")

st.markdown(f"""
<div style='background:linear-gradient(135deg,{COLORS["primary"]}22,{COLORS["card_bg"]});
            border-left:4px solid {COLORS["primary"]};
            padding:1.5rem 2rem; border-radius:12px; margin-bottom:1.5rem;'>
  <h1 style='margin:0; color:{COLORS["primary"]}'>🃏 Active Recall Flashcards</h1>
  <p style='margin:0.3rem 0 0; color:{COLORS["text_muted"]}'>
    Feynman analogies & active recall prompts — test yourself before flipping!
  </p>
</div>
""", unsafe_allow_html=True)

topic_tree = st.session_state.get("topic_tree", {})
topics = topic_tree.get("topics", [])

col1, col2 = st.columns([2, 1])
with col1:
    if topics:
        topic_options = {f"{t['id']} — {t['title']}": t for t in topics}
        selected_key = st.selectbox("Select Topic", list(topic_options.keys()))
        selected_topic = topic_options[selected_key]
        topic_id = selected_topic["id"]
        topic_title = selected_topic["title"]
    else:
        topic_id = st.text_input("Topic ID", value="t1")
        topic_title = st.text_input("Topic Title", placeholder="e.g. TCP vs UDP Protocol")

with col2:
    num_cards = st.slider("Number of Flashcards", 3, 10, 5)

if st.button("✨ Generate Flashcards", type="primary", use_container_width=True, disabled=not topic_title):
    with st.spinner(f"Creating Feynman-style flashcards for {topic_title}..."):
        try:
            prompt = flashcard_generator_prompt(topic_id, topic_title, num_cards)
            result = call_gemini_json(prompt, temperature=0.6)
            st.session_state["flashcards"] = result
            st.session_state["card_index"] = 0
            st.session_state["show_answer"] = False
            save_persistent_state(st.session_state)
            st.rerun()
        except Exception as e:
            st.error(f"Failed to generate flashcards: {e}")

# ── Display Active Flashcard Deck ──────────────────────────────────────────────
if "flashcards" in st.session_state and st.session_state["flashcards"].get("cards"):
    deck = st.session_state["flashcards"]
    cards = deck.get("cards", [])
    idx = st.session_state.get("card_index", 0)

    if idx >= len(cards):
        idx = 0
        st.session_state["card_index"] = 0

    curr = cards[idx]
    show_back = st.session_state.get("show_answer", False)

    st.divider()
    prog = (idx + 1) / len(cards)
    st.progress(prog, text=f"Card {idx+1} of {len(cards)}")

    # Card Display Area
    if not show_back:
        st.markdown(f"""
<div style='background:{COLORS["card_bg"]}; border:2px solid {COLORS["primary"]};
            border-radius:16px; padding:2.5rem 2rem; min-height:220px;
            display:flex; flex-direction:column; justify-content:center; align-items:center;
            text-align:center; box-shadow:0 8px 24px rgba(0,0,0,0.3);'>
  <span style='font-size:0.8rem; text-transform:uppercase; letter-spacing:1px; color:{COLORS["text_muted"]}; margin-bottom:1rem;'>
    🤔 Prompt / Question
  </span>
  <h3 style='margin:0; font-weight:600; line-height:1.4;'>{curr.get("front","")}</h3>
</div>
""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
<div style='background:{COLORS["card_bg"]}; border:2px solid {COLORS["success"]};
            border-radius:16px; padding:2rem; min-height:220px;
            box-shadow:0 8px 24px rgba(0,0,0,0.3);'>
  <span style='font-size:0.8rem; text-transform:uppercase; letter-spacing:1px; color:{COLORS["success"]}; margin-bottom:0.5rem; display:block;'>
    💡 Feynman Explanation & Core Mechanism
  </span>
  <p style='font-size:1.05rem; line-height:1.5; margin:0.5rem 0;'>{curr.get("back","")}</p>
  <div style='background:{COLORS["bg_dark"]}; padding:0.8rem 1rem; border-radius:8px; margin-top:1rem; border-left:3px solid {COLORS["warning"]};'>
    <strong style='color:{COLORS["warning"]}; font-size:0.85rem;'>📌 Key Takeaway:</strong>
    <span style='font-size:0.9rem; margin-left:0.5rem;'>{curr.get("key_takeaway","")}</span>
  </div>
</div>
""", unsafe_allow_html=True)

    st.write("")

    # Card Control Buttons
    c_prev, c_flip, c_next = st.columns([1, 2, 1])
    with c_prev:
        if st.button("⬅️ Previous", disabled=(idx == 0), use_container_width=True):
            st.session_state["card_index"] = max(0, idx - 1)
            st.session_state["show_answer"] = False
            st.rerun()

    with c_flip:
        flip_label = "🔄 Flip to Question" if show_back else "👁️ Reveal Explanation"
        if st.button(flip_label, type="primary", use_container_width=True):
            st.session_state["show_answer"] = not show_back
            st.rerun()

    with c_next:
        if st.button("Next ➡️", disabled=(idx == len(cards) - 1), use_container_width=True):
            st.session_state["card_index"] = min(len(cards) - 1, idx + 1)
            st.session_state["show_answer"] = False
            st.rerun()

    # Spaced Repetition Mastery Rating (shown after flip)
    if show_back:
        st.divider()
        st.markdown("<p style='text-align:center; color:#aaa; font-size:0.9rem;'>How well did you know this concept?</p>", unsafe_allow_html=True)
        r1, r2, r3 = st.columns(3)
        with r1:
            if st.button("🔴 Hard (Review Soon)", use_container_width=True):
                if idx < len(cards) - 1:
                    st.session_state["card_index"] += 1
                    st.session_state["show_answer"] = False
                st.rerun()
        with r2:
            if st.button("🟡 Good (Understood)", use_container_width=True):
                if idx < len(cards) - 1:
                    st.session_state["card_index"] += 1
                    st.session_state["show_answer"] = False
                st.rerun()
        with r3:
            if st.button("🟢 Easy (Mastered)", use_container_width=True):
                if idx < len(cards) - 1:
                    st.session_state["card_index"] += 1
                    st.session_state["show_answer"] = False
                st.rerun()

