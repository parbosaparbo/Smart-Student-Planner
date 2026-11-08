"""
StudyMind AI — Page 10: Student Progress & Visual Analytics
Comprehensive mastery charts, study time distribution, and AI growth diagnostic
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import date, datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from ui_components import render_sidebar_header, nav_to_dashboard
from gemini_client import call_gemini_text
from config import COLORS

st.set_page_config(page_title="Progress Tracker — StudyMind AI", page_icon="📈", layout="wide", initial_sidebar_state="expanded")
render_sidebar_header()

st.markdown(f"""
<div style='background:linear-gradient(135deg,{COLORS["primary"]}22,{COLORS["card_bg"]});
            border-left:4px solid {COLORS["primary"]};
            padding:1.5rem 2rem; border-radius:12px; margin-bottom:1.5rem;'>
  <h1 style='margin:0; color:{COLORS["primary"]}'>📈 Student Progress & Analytics</h1>
  <p style='margin:0.3rem 0 0; color:{COLORS["text_muted"]}'>
    Visualize your preparation, topic-by-topic mastery, and AI readiness trajectory.
  </p>
</div>
""", unsafe_allow_html=True)

student = st.session_state.get("student_profile", {})
student_name = student.get("student_name", "Student")
topic_tree = st.session_state.get("topic_tree", {})
quiz_results = st.session_state.get("quiz_results", [])
schedule = st.session_state.get("schedule", {})

# ── If no data yet ─────────────────────────────────────────────────────────────
if not student and not quiz_results:
    st.info("👋 Set up your profile or load the 7th Sem Demo on the Dashboard to see your analytics!")
    if st.button("🏠 Go to Dashboard"):
        nav_to_dashboard()
    st.stop()

# ── Top Metrics Banner ─────────────────────────────────────────────────────────
topics_list = topic_tree.get("topics", [])
total_topics = len(topics_list)

mastery_scores = [r.get("score_pct", 0) for r in quiz_results]
avg_mastery = round(sum(mastery_scores) / len(mastery_scores)) if mastery_scores else 0

mastered_count = sum(1 for s in mastery_scores if s >= 70)
weak_count = sum(1 for s in mastery_scores if s < 70)

days_left = 0
if student.get("exam_date"):
    try:
        exam_dt = datetime.strptime(student["exam_date"], "%Y-%m-%d").date()
        days_left = max(0, (exam_dt - date.today()).days)
    except Exception:
        pass

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("🎯 Overall Mastery", f"{avg_mastery}%", delta=f"{avg_mastery - 70}% vs target" if avg_mastery else None)
kpi2.metric("✅ Mastered Topics", f"{mastered_count} / {len(quiz_results) if quiz_results else total_topics}")
kpi3.metric("🚨 Topics Needing Work", weak_count)
kpi4.metric("⏳ Days to Exam", f"{days_left} days")

st.divider()

# ── Graph Row 1: Gauge Chart & Topic Score Bar Chart ──────────────────────────
g_col1, g_col2 = st.columns([1, 2], gap="medium")

with g_col1:
    st.subheader("🎯 Mastery Gauge")
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=avg_mastery,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Exam Readiness", 'font': {'size': 18, 'color': 'white'}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
            'bar': {'color': COLORS["primary"], 'thickness': 0.3},
            'bgcolor': "rgba(0,0,0,0)",
            'borderwidth': 2,
            'bordercolor': "#333",
            'steps': [
                {'range': [0, 50], 'color': 'rgba(231, 76, 60, 0.3)'},
                {'range': [50, 70], 'color': 'rgba(243, 156, 18, 0.3)'},
                {'range': [70, 100], 'color': 'rgba(46, 204, 113, 0.3)'},
            ],
            'threshold': {
                'line': {'color': "white", 'width': 3},
                'thickness': 0.8,
                'value': 70
            }
        },
        number={'suffix': "%", 'font': {'size': 40, 'color': COLORS["primary"]}}
    ))
    fig_gauge.update_layout(
        height=280,
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white")
    )
    st.plotly_chart(fig_gauge, width="stretch")

with g_col2:
    st.subheader("📊 Topic-by-Topic Performance")
    if quiz_results:
        t_names = [r.get("topic_title", "Topic")[:28] for r in quiz_results]
        t_scores = [r.get("score_pct", 0) for r in quiz_results]
        bar_colors = [
            COLORS["success"] if s >= 70 else COLORS["warning"] if s >= 50 else COLORS["danger"]
            for s in t_scores
        ]

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=t_names,
            y=t_scores,
            marker_color=bar_colors,
            text=[f"{s}%" for s in t_scores],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Score: %{y}%<extra></extra>"
        ))
        fig_bar.add_hline(
            y=70, line_dash="dash", line_color="rgba(255,255,255,0.7)",
            annotation_text="70% Mastery Target", annotation_position="top right"
        )
        fig_bar.update_layout(
            height=280,
            margin=dict(l=10, r=10, t=30, b=20),
            yaxis=dict(range=[0, 115], title="Accuracy Score (%)", gridcolor="rgba(255,255,255,0.08)"),
            xaxis=dict(title="Topics Tested", tickangle=-15),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white")
        )
        st.plotly_chart(fig_bar, width="stretch")
    else:
        st.info("📝 Take at least 1 quiz to populate your topic performance graph!")

st.divider()

# ── Graph Row 2: Study Hours Allocation & Performance Trend ───────────────────
row2_c1, row2_c2 = st.columns([1, 1], gap="medium")

with row2_c1:
    st.subheader("⏱️ Syllabus Study Hours Distribution")
    if topics_list:
        labels = [t.get("title", f"Topic {i+1}")[:25] for i, t in enumerate(topics_list)]
        hours = [t.get("estimated_hours", 4.0) for t in topics_list]

        fig_donut = go.Figure(data=[go.Pie(
            labels=labels,
            values=hours,
            hole=0.45,
            marker=dict(colors=[
                COLORS["primary"], COLORS["info"], COLORS["success"],
                COLORS["warning"], COLORS["danger"], "#9B59B6"
            ]),
            textinfo="label+percent",
            insidetextorientation="radial"
        )])
        fig_donut.update_layout(
            height=320,
            margin=dict(l=10, r=10, t=20, b=20),
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
            showlegend=False
        )
        st.plotly_chart(fig_donut, width="stretch")
    else:
        st.info("Parse your syllabus to view your study hours breakdown.")

with row2_c2:
    st.subheader("📈 Active Recall Score Trend")
    if len(quiz_results) >= 2:
        df_trend = pd.DataFrame({
            "Attempt": [f"Quiz {i+1}: {r.get('topic_title','')[:15]}" for i, r in enumerate(quiz_results)],
            "Score": [r.get("score_pct", 0) for r in quiz_results]
        })
        fig_line = px.line(
            df_trend, x="Attempt", y="Score",
            markers=True,
            line_shape="spline"
        )
        fig_line.update_traces(
            line_color=COLORS["primary"],
            line_width=3,
            marker=dict(size=10, color=COLORS["success"])
        )
        fig_line.add_hline(y=70, line_dash="dash", line_color="white", annotation_text="70% Target")
        fig_line.update_layout(
            height=320,
            margin=dict(l=10, r=10, t=20, b=20),
            yaxis=dict(range=[0, 105], gridcolor="rgba(255,255,255,0.08)"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white")
        )
        st.plotly_chart(fig_line, width="stretch")
    elif quiz_results:
        st.info("Take 1 more quiz to generate your progress timeline graph!")
    else:
        st.info("Quiz history will plot your retention curve here.")

st.divider()

# ── AI Growth Diagnostic ───────────────────────────────────────────────────────
st.subheader("🧠 StudyMind AI Diagnostic Audit")
st.caption("Get an honest, evidence-based performance review from your academic coach.")

if st.button("🔍 Generate AI Progress Diagnostic", type="primary", width="stretch"):
    with st.spinner("Analyzing your preparation velocity and mastery curves..."):
        audit_prompt = f"""You are StudyMind AI, an elite academic strategist.
Analyze this student's progress and write a 3-paragraph diagnostic audit:
- Student Name: {student_name}
- Subject: {student.get('subject', 'General')}
- Days Left: {days_left}
- Average Mastery: {avg_mastery}%
- Quiz History: {quiz_results}

FORMAT:
1. Honest Assessment: Where they stand realistically.
2. High-Leverage Priority: The single biggest concept gap or opportunity to gain 10-15 marks.
3. 7-Day Strategy: Concrete action plan. Warm, motivational, truthful (no false hope).
"""
        diagnostic = call_gemini_text(audit_prompt, temperature=0.7)
        st.session_state["progress_diagnostic"] = diagnostic

if "progress_diagnostic" in st.session_state:
    st.markdown(f"""
<div style='background:{COLORS["card_bg"]}; border-left:4px solid {COLORS["primary"]};
            border-radius:12px; padding:1.8rem; margin-top:1rem;'>
  {st.session_state["progress_diagnostic"]}
</div>
""", unsafe_allow_html=True)

