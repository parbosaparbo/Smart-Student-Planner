# 🧠 StudyMind AI — Smart Study Planner

> An intelligent, empathetic, and strict AI-powered academic coach built with **Python**, **Streamlit**, and the **Gemini API**.

---

## 🌟 What is StudyMind AI?

StudyMind AI combines the expertise of a world-class tutor, exam strategist, and cognitive learning scientist into a personal academic coach. It uses evidence-based methods:

- **Spaced Repetition** — optimal review intervals to beat the forgetting curve
- **Active Recall** — high-stakes, scenario-based MCQs (no Googleable definitions)
- **Feynman Technique** — simple analogies and mental models to lock in hard concepts
- **Interleaving** — smart topic mixing to build flexible problem-solving skills
- **Socratic Tutoring** — guides students to answers step-by-step; never spoon-feeds

---

## ⚡ Core Features

| Feature | Description | Output Format |
|---|---|---|
| 📚 **Syllabus Parser** | Upload PDF or paste text → structured topic tree with Bloom's taxonomy difficulties & priorities | Raw JSON |
| 📅 **Schedule Generator** | 70% new topics / 20% weak spot revision / 10% mocks. Peak focus mornings, mandatory rest days | Raw JSON |
| 🎯 **AI Quiz Generator** | Scenario-based questions with plausible distractors (common misconceptions). Timed 60–90s | Raw JSON |
| 📊 **Weak Spot Analyzer** | Finds critical gaps (<50%), high-risk areas, and **blind spots** (high confidence, low score) | Raw JSON |
| 🔄 **Smart Rescheduler** | Surgical reschedule triggered when topic score <70%. Human-in-the-loop confirmation | Raw JSON |
| 💬 **Doubt Solver** | Socratic chatbot — gives analogies and guiding questions, never raw exam answers | Markdown |
| 📝 **Mock Exam** | Timed simulation with speed-integrity detection, letter grades, and exam readiness % | Raw JSON |
| 🌅 **Daily Briefing** | Personalized 150-word morning briefing rendered in clean Streamlit markdown | Markdown |

---

## 🛠️ MCP Tools Included

StudyMind AI implements 5 dedicated tools in `mcp_tools.py`:

```python
generate_quiz(topic_id, num_questions)         # fresh AI quiz for any topic
reschedule_weak_topic(topic_id, reason)        # adjusts study plan for low scores
search_syllabus(query)                         # RAG search over uploaded syllabus
push_to_calendar(study_block_id)               # 1-click Google Calendar sync
analyze_weak_spots(student_id)                 # full mastery breakdown & blind spots
```

---

## 🚀 Quick Start

### 1. Clone & Navigate
```bash
cd "c:\Users\deshr\Documents\STUDY PLANNER 7 TH SEM"
```

### 2. Set up your Gemini API Key
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Open `.env` and add your Google Gemini API key:
```env
GEMINI_API_KEY=AIzaSy...your_key_here
```
> Get a free API key at: [Google AI Studio](https://aistudio.google.com/)

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run as Native Desktop App 🖥️

**Option A (Recommended — 1-Click Silent Desktop Launch):**
Double-click [`StudyMind_AI.vbs`](file:///c:/Users/deshr/Documents/STUDY%20PLANNER%207%20TH%20SEM/StudyMind_AI.vbs) or [`run.bat`](file:///c:/Users/deshr/Documents/STUDY%20PLANNER%207%20TH%20SEM/run.bat).
This launches a standalone, borderless native desktop window powered by `pywebview` / native desktop wrapper (no browser tabs, no URL bar).

**Option B (Terminal Launcher):**
```bash
python desktop.py
```

**Option C (Standard Browser Mode):**
```bash
streamlit run Dashboard.py
```

---

## 📁 Project Structure

```
STUDY PLANNER 7 TH SEM/
├── Dashboard.py                # Main entry point & student dashboard
├── config.py                   # App constants, colors, thresholds, labels
├── prompts.py                  # All 8 Gemini prompt builders (strict JSON rules)
├── gemini_client.py            # Gemini API client with JSON stripping & validation
├── mcp_tools.py                # 5 MCP tools (quiz, reschedule, RAG search, cal, analyzer)
├── requirements.txt            # Pinned dependencies
├── .env.example                # API key template
├── .gitignore                  # Standard Python + Streamlit gitignore
├── .streamlit/
│   └── config.toml             # Custom dark theme configuration
└── pages/
    ├── 1_📚_Syllabus_Parser.py     # PDF & text syllabus parser
    ├── 2_📅_Schedule_Generator.py  # 70/20/10 study plan builder
    ├── 3_🎯_Quiz.py                # Scenario-based active recall quiz
    ├── 4_📊_Weak_Spot_Analyzer.py  # Blind spot detection & auto-rescheduler
    ├── 5_💬_Doubt_Solver.py        # Socratic tutor chatbot (live streaming)
    ├── 6_📝_Mock_Exam.py           # Timed full exam with integrity flag & parallel generation
    ├── 7_🌅_Daily_Briefing.py      # Personalized 150-word morning briefing (live streaming)
    ├── 8_🃏_Flashcards.py          # 3D interactive flashcards with Leitner spaced repetition
    ├── 9_⏱️_Focus_Timer.py          # Pomodoro focus & flow timer tied to today's schedule
    └── 10_📈_Student_Progress.py   # Comprehensive Plotly visual progress charts & AI audit
```

---

## 🛡️ Iron-Clad Rules Built In

1. **Raw JSON Only** — Structured prompts return pure JSON with no markdown fences (` ```json `), preventing parsing errors
2. **Strict Socratic Tutoring** — Never gives direct answers to quiz/exam questions
3. **No Silent Changes** — The smart rescheduler always requires Human-in-the-Loop (`hitl_message`) student confirmation
4. **Auto-Reschedule Trigger** — Scoring <70% on any topic immediately recommends surgical schedule adjustments
5. **No False Hope** — If an exam is close and mastery is low, StudyMind is honest and constructive
6. **Multi-Language Support** — Responds in English, Hindi, Hinglish, or whichever language the student uses

