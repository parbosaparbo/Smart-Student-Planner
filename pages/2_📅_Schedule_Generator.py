"""
StudyMind AI — Page 2: Schedule Generator
"""
import streamlit as st
import json
import pandas as pd
from datetime import date, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from gemini_client import call_gemini_json
from core.scheduler import generate_fast_schedule
from prompts import schedule_generator_prompt
from mcp_tools import push_to_calendar
from ui_components import render_sidebar_header, render_gcal_sidebar_status
from storage import save_persistent_state
from config import COLORS
import google_calendar as gcal

st.set_page_config(page_title="Schedule Generator — StudyMind AI", page_icon="📅", layout="wide", initial_sidebar_state="expanded")
render_sidebar_header()
render_gcal_sidebar_status()

# ── OAuth callback handler ──────────────────────────────────────────────────────
# When Google redirects back with ?code=...&state=..., exchange the code for a token.
_oauth_code = st.query_params.get("code")
_oauth_state = st.query_params.get("state")
if _oauth_code:
    try:
        _student_key = _oauth_state or st.session_state.get("student_profile", {}).get("student_name", "Student")
        gcal.exchange_code_for_token(_oauth_code, _student_key)
        st.query_params.clear()
        st.session_state["gcal_just_connected"] = True
        st.rerun()
    except Exception as e:
        st.query_params.clear()
        st.error(f"❌ Google Calendar connection failed: {e}")

if st.session_state.pop("gcal_just_connected", False):
    st.toast("✅ Google Calendar connected successfully!", icon="📅")

st.markdown(f"""
<div style='background:linear-gradient(135deg,{COLORS["info"]}22,{COLORS["card_bg"]});
            border-left:4px solid {COLORS["info"]};
            padding:1.5rem 2rem; border-radius:12px; margin-bottom:1.5rem;'>
  <h1 style='margin:0; color:{COLORS["info"]}'>📅 Study Schedule Generator</h1>
  <p style='margin:0.3rem 0 0; color:{COLORS["text_muted"]}'>
    Tell StudyMind about yourself — get a personalized day-by-day study plan.
  </p>
</div>
""", unsafe_allow_html=True)

# ── Check prerequisites ────────────────────────────────────────────────────────
if "topic_tree" not in st.session_state:
    st.warning("⚠️ No topic tree found. Please parse your syllabus first.")
    if st.button("Go to Syllabus Parser"):
        st.switch_page("pages/1_📚_Syllabus_Parser.py")
    st.stop()

topic_tree = st.session_state["topic_tree"]

# ── Student Profile Form ───────────────────────────────────────────────────────
st.subheader("🎓 Student Profile")
saved_prof = st.session_state.get("student_profile", {})

with st.form("student_profile_form"):
    c1, c2 = st.columns(2)
    with c1:
        default_name = saved_prof.get("student_name", "")
        name = st.text_input("Your Name", value=default_name, placeholder="e.g. Riya")
        
        default_exam_val = date.today() + timedelta(days=14)
        if saved_prof.get("exam_date"):
            try:
                from datetime import datetime as dt
                default_exam_val = dt.strptime(saved_prof["exam_date"], "%Y-%m-%d").date()
            except Exception:
                pass
        exam_date = st.date_input("Exam Date", value=default_exam_val, min_value=date.today())
        
        default_hrs = float(saved_prof.get("daily_hours", 4.0))
        daily_hrs = st.slider("Daily Study Hours", min_value=1.0, max_value=12.0, value=default_hrs, step=0.5)
        
        lvl_options = ["beginner", "intermediate", "advanced"]
        lvl_idx = lvl_options.index(saved_prof.get("current_level", "intermediate")) if saved_prof.get("current_level") in lvl_options else 1
        level = st.selectbox("Current Level", lvl_options, index=lvl_idx)

    with c2:
        default_pref = saved_prof.get("preferred_times", ["morning", "evening"])
        pref_times = st.multiselect(
            "Preferred Study Times",
            ["early_morning", "morning", "afternoon", "evening", "night"],
            default=default_pref
        )
        default_blocked = saved_prof.get("blocked_days", ["sunday"])
        blocked_days = st.multiselect(
            "Days You Can't Study (blocked)",
            ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"],
            default=default_blocked
        )
        known_topics_str = ", ".join(saved_prof.get("known_topics", []))
        known_topics = st.text_input(
            "Topics you already know (comma-separated)",
            value=known_topics_str,
            placeholder="e.g. Arrays, Sorting"
        )
        styles = ["visual", "reading/writing", "auditory", "kinesthetic", "mixed"]
        style_idx = styles.index(saved_prof.get("learning_style", "mixed")) if saved_prof.get("learning_style") in styles else 4
        learning_style = st.selectbox(
            "Learning Style",
            styles,
            index=style_idx
        )

    submitted = st.form_submit_button("🚀 Generate My Study Plan", type="primary", width="stretch")

if submitted:
    days_left = (exam_date - date.today()).days
    if days_left < 7:
        st.warning(
            f"⚠️ That's very tight — only **{days_left} days** left! "
            "We'll need to prioritize ruthlessly. I'll build you an intense plan."
        )

    student_profile = {
        "student_name":   name or "Student",
        "subject":        topic_tree.get("subject", ""),
        "exam_date":      str(exam_date),
        "daily_hours":    daily_hrs,
        "preferred_times": pref_times,
        "blocked_days":   blocked_days,
        "current_level":  level,
        "known_topics":   [t.strip() for t in known_topics.split(",") if t.strip()],
        "learning_style": learning_style,
    }

    st.session_state["student_profile"] = student_profile

    with st.spinner("⚡ Assembling sub-2.5s hybrid study schedule..."):
        try:
            schedule = generate_fast_schedule(student_profile, topic_tree, str(date.today()))
            st.session_state["schedule"] = schedule
            save_persistent_state(st.session_state)
            st.success("✅ Study plan generated in under 2.5s!")

            # ── Automatically sync to Google Calendar if connected ─────────────
            s_key = student_profile.get("student_name", "Student")
            if gcal.is_connected(s_key):
                try:
                    sync_res = gcal.sync_schedule_to_calendar(schedule, s_key, s_key)
                    st.session_state["gcal_event_map"] = sync_res
                    save_persistent_state(st.session_state)
                    total_synced = sync_res.get("created", 0) + sync_res.get("updated", 0)
                    st.toast(f"📅 Auto-synced {total_synced} sessions to Google Calendar!", icon="📅")
                except Exception as sync_err:
                    st.info(f"💡 Schedule generated! Google Calendar notice: {sync_err}")
        except Exception as e:
            st.error(f"❌ Failed to generate schedule: {e}")
            st.stop()

# ── Display Schedule ───────────────────────────────────────────────────────────
if "schedule" in st.session_state:
    schedule = st.session_state["schedule"]
    summary  = schedule.get("schedule_summary", {})

    st.divider()
    st.subheader("📊 Schedule Summary")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Study Hours", f"{summary.get('total_study_hours', 0)}h")
    m2.metric("Rest Days", len(summary.get("rest_days", [])))
    m3.metric("Mock Test Days", len(summary.get("mock_test_days", [])))
    m4.metric("Revision Starts", summary.get("revision_start_date", "—"))

    st.divider()
    
    view_c1, view_c2 = st.columns([1, 1])
    with view_c1:
        st.subheader("📆 Study Plan")
    with view_c2:
        view_mode = st.radio("View Mode", ["📋 Detailed List", "📅 Visual Calendar"], horizontal=True, label_visibility="collapsed")

    daily = schedule.get("daily_blocks", [])
    day_type_colors = {
        "study":     COLORS["primary"],
        "revision":  COLORS["warning"],
        "mock_test": COLORS["danger"],
        "rest":      COLORS["success"],
    }
    day_type_icons = {"study": "📖", "revision": "🔄", "mock_test": "📝", "rest": "😴"}

    if view_mode == "📅 Visual Calendar":
        calendar_events = []
        for day in daily:
            d_str = day.get("date", "")
            d_type = day.get("day_type", "study")
            b_color = day_type_colors.get(d_type, COLORS["primary"])

            blocks = day.get("blocks", [])
            if not blocks:
                calendar_events.append({
                    "title": "😴 Rest Day",
                    "start": d_str,
                    "allDay": True,
                    "backgroundColor": COLORS["success"],
                    "borderColor": COLORS["success"],
                })
            else:
                for blk in blocks:
                    start_t = blk.get("start_time", "09:00")
                    dur = int(blk.get("duration_minutes", 60))
                    start_iso = f"{d_str}T{start_t}:00"
                    try:
                        from datetime import datetime as dt, timedelta as td
                        dt_s = dt.strptime(start_iso, "%Y-%m-%dT%H:%M:%S")
                        dt_e = dt_s + td(minutes=dur)
                        end_iso = dt_e.strftime("%Y-%m-%dT%H:%M:%S")
                    except Exception:
                        end_iso = start_iso
                    calendar_events.append({
                        "title": f"{blk.get('topic_title','')} ({dur}m)",
                        "start": start_iso,
                        "end": end_iso,
                        "backgroundColor": b_color,
                        "borderColor": b_color,
                    })
        try:
            from streamlit_calendar import calendar
            cal_options = {
                "headerToolbar": {
                    "left": "prev,next today",
                    "center": "title",
                    "right": "dayGridMonth,timeGridWeek,timeGridDay",
                },
                "initialView": "dayGridMonth",
                "navLinks": True,
                "selectable": True,
            }
            calendar(events=calendar_events, options=cal_options, custom_css="""
                .fc-event { border-radius: 4px; font-size: 0.85rem; padding: 2px 4px; }
            """)
        except Exception as e:
            st.warning(f"Calendar view note: {e}")

    else:
        for day in daily:
            d_type  = day.get("day_type", "study")
            d_color = day_type_colors.get(d_type, COLORS["primary"])
            d_icon  = day_type_icons.get(d_type, "📖")
            blocks  = day.get("blocks", [])

            with st.expander(
                f"{d_icon} **{day.get('date','')}** — {d_type.replace('_',' ').title()} "
                f"({len(blocks)} block{'s' if len(blocks)!=1 else ''})"
            ):
                if not blocks:
                    st.markdown(f"*{d_icon} Rest day — recharge!*")
                else:
                    for blk in blocks:
                        blk_copy = dict(blk)
                        blk_copy["date"] = day.get("date", "")
                        cal_data = push_to_calendar(blk_copy)
                        cal_url  = cal_data.get("google_calendar_url", "#")
                        st.markdown(f"""
<div style='border-left:3px solid {d_color}; padding:0.6rem 1rem; margin:0.5rem 0;
            background:{COLORS["card_bg"]}; border-radius:8px;'>
  <div style='display:flex; justify-content:space-between; align-items:center;'>
    <span><strong>{blk.get('start_time','')}</strong> · {blk.get('topic_title','')} · <em>{blk.get('duration_minutes',0)} min</em></span>
    <a href='{cal_url}' target='_blank' style='color:{COLORS["primary"]}; font-size:0.8rem; text-decoration:none;'>📅 Add to Google Calendar ↗</a>
  </div>
  <small style='color:#ccc;'>🎯 {blk.get('session_goal','')}</small><br>
  <small style='color:{COLORS["text_muted"]};'>💡 {blk.get('resources_tip','')}</small>
</div>
""", unsafe_allow_html=True)

    st.divider()
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.download_button(
            "⬇️ Download Schedule (JSON)",
            data=json.dumps(schedule, indent=2),
            file_name="study_schedule.json",
            mime="application/json",
            width="stretch",
        )
    with col_b:
        md_text = f"# 📅 StudyMind AI — Study Schedule\n\n"
        md_text += f"**Total Hours:** {summary.get('total_study_hours', 0)}h | **Revision Starts:** {summary.get('revision_start_date', '—')}\n\n---\n\n"
        for day in daily:
            md_text += f"### {day.get('date','')} — {day.get('day_type','study').upper()}\n"
            if not day.get("blocks"):
                md_text += "- *Rest Day — Recharge!*\n\n"
            for b in day.get("blocks", []):
                md_text += f"- **{b.get('start_time','')}** ({b.get('duration_minutes', 60)}m): {b.get('topic_title','')}\n"
                md_text += f"  - 🎯 Goal: {b.get('session_goal','')}\n"
                md_text += f"  - 💡 Tip: {b.get('resources_tip','')}\n"
            md_text += "\n"
        st.download_button(
            "📄 Export Printable Plan (.md)",
            data=md_text,
            file_name="printable_study_plan.md",
            mime="text/markdown",
            width="stretch",
        )
    with col_c:
        if st.button("➡️ Take a Quiz Now", width="stretch"):
            st.switch_page("pages/3_🎯_Quiz.py")

    # ── Google Calendar Sync Section ────────────────────────────────────────────
    st.divider()
    st.subheader("📅 Google Calendar Sync")

    student_key = st.session_state.get("student_profile", {}).get("student_name", "Student")
    student_name = student_key

    if not gcal.is_configured():
        st.info(
            "**Google Calendar sync is not configured yet.**\n\n"
            "To enable it:\n"
            "1. Go to [Google Cloud Console](https://console.cloud.google.com/) → Create a project\n"
            "2. Enable the **Google Calendar API**\n"
            "3. Create **OAuth 2.0 Credentials** (Web application)\n"
            "4. Add `http://localhost:8501` as an **Authorized redirect URI**\n"
            "5. Copy the Client ID and Client Secret into your `.env` file:\n"
            "   ```\n"
            "   GOOGLE_CLIENT_ID=your_client_id\n"
            "   GOOGLE_CLIENT_SECRET=your_client_secret\n"
            "   ```\n"
            "6. Restart the app.\n\n"
            "💡 *You can still use the per-block \"Add to Google Calendar ↗\" links above without OAuth.*"
        )
    elif gcal.is_connected(student_key):
        # Connected — show status and Sync Now / Disconnect buttons
        gcal_col1, gcal_col2 = st.columns([3, 1])
        with gcal_col1:
            email = gcal.get_connected_account_email(student_key)
            if email:
                st.success(f"✅ Connected to Google Calendar as **{email}**")
            else:
                st.success("✅ Google Calendar connected")
            st.caption("🔔 Reminders: 10-minute popup & email notifications will alert you on Android, iPhone & Desktop.")
        with gcal_col2:
            if st.button("🔌 Disconnect", width="stretch", key="gcal_disconnect"):
                gcal.delete_token(student_key)
                st.toast("Disconnected from Google Calendar.", icon="🔌")
                st.rerun()

        sync_col1, sync_col2 = st.columns(2)
        with sync_col1:
            if st.button("⚡ Sync Now", type="primary", width="stretch", key="gcal_sync_now"):
                with st.spinner("Syncing schedule with 10-minute reminders to Google Calendar..."):
                    try:
                        result = gcal.sync_schedule_to_calendar(schedule, student_key, student_name)
                        st.session_state["gcal_event_map"] = result
                        save_persistent_state(st.session_state)
                        if result["errors"]:
                            st.warning(
                                f"⚠️ Synced with {len(result['errors'])} error(s):\n"
                                + "\n".join(f"- {e}" for e in result["errors"][:5])
                            )
                        else:
                            st.success(
                                f"✅ Synced! **{result['created']}** created, "
                                f"**{result['updated']}** updated, "
                                f"**{result['skipped']}** rest days skipped."
                            )
                            st.balloons()
                    except ValueError as e:
                        st.error(f"❌ {e}")
                    except Exception as e:
                        st.error(f"❌ Sync failed: {e}")
        with sync_col2:
            if st.button("🗑️ Remove All Synced Events", width="stretch", key="gcal_delete_all"):
                with st.spinner("Removing StudyMind events from Google Calendar..."):
                    try:
                        count = gcal.delete_all_synced_events(student_key)
                        st.success(f"✅ Removed {count} events from Google Calendar.")
                    except Exception as e:
                        st.error(f"❌ Failed to remove events: {e}")

        # Show last sync summary if available
        last_sync = st.session_state.get("gcal_event_map")
        if last_sync and isinstance(last_sync, dict):
            with st.expander("📊 Last Sync Summary"):
                ls1, ls2, ls3, ls4 = st.columns(4)
                ls1.metric("Created", last_sync.get("created", 0))
                ls2.metric("Updated", last_sync.get("updated", 0))
                ls3.metric("Skipped", last_sync.get("skipped", 0))
                ls4.metric("Total Blocks", last_sync.get("total_blocks", 0))
    else:
        # Not connected — check if scopes changed on existing token
        has_mismatch, missing_s = gcal.has_scope_mismatch(student_key)
        if has_mismatch:
            st.warning(
                f"⚠️ **Google Calendar permissions updated:** StudyMind AI now requires updated scopes "
                f"(`{', '.join(missing_s)}`). Please click Connect below to re-authenticate and regenerate your token with the new scopes."
            )

        # Not connected — show connect buttons & authorization flows
        _muted = COLORS['text_muted']
        st.markdown(
            f"<p style='color:{_muted};'>Connect your Google account to automatically "
            f"sync study sessions with <b>10-minute reminders</b> that work on Android &amp; iPhone even when your laptop is turned off.</p>",
            unsafe_allow_html=True,
        )

        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            if st.button("🔗 Connect Google Calendar (Instant)", type="primary", width="stretch", key="gcal_connect_local"):
                with st.spinner("Opening browser for Google authorization... Please grant permission in the opened tab."):
                    success, msg = gcal.connect_via_local_server(student_key)
                    if success:
                        st.session_state["gcal_just_connected"] = True
                        st.rerun()
                    else:
                        st.error(f"❌ Connection error: {msg}")
        with c_btn2:
            if st.button("🌐 Browser Link / Paste Code", width="stretch", key="gcal_toggle_manual"):
                st.session_state["show_gcal_auth"] = not st.session_state.get("show_gcal_auth", False)

        if st.session_state.get("show_gcal_auth", False):
            try:
                auth_url, state = gcal.build_auth_url(student_key)
                st.markdown(
                    f"""
                    <div style='background:{COLORS["card_bg"]}; border-radius:10px; padding:1.2rem; border:1px solid rgba(255,255,255,0.1); margin:1rem 0;'>
                      <h4 style='margin:0 0 0.5rem;'>Sign in with Google</h4>
                      <p style='color:{COLORS["text_muted"]}; font-size:0.9rem;'>
                        Click the button below to sign in. After authorizing, if the tab redirects to localhost, copy the URL or code and paste it below.
                      </p>
                      <a href='{auth_url}' target='_blank' style='display:inline-block; padding:0.6rem 1.5rem; 
                         background:{COLORS["primary"]}; color:white; border-radius:8px; 
                         text-decoration:none; font-weight:600; margin-bottom:1rem;'>🔐 Open Google Sign-In ↗</a>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                
                st.caption("Paste the redirected URL or authorization code here:")
                manual_code_input = st.text_input("Authorization Code or URL", placeholder="Paste code or http://localhost:8501/?code=...", key="manual_gcal_code")
                if st.button("Verify & Connect", type="primary", key="manual_gcal_submit") and manual_code_input.strip():
                    raw_code = manual_code_input.strip()
                    if "code=" in raw_code:
                        import urllib.parse
                        parsed = urllib.parse.urlparse(raw_code)
                        q = urllib.parse.parse_qs(parsed.query)
                        raw_code = q.get("code", [raw_code])[0]
                    try:
                        gcal.exchange_code_for_token(raw_code, student_key)
                        st.session_state["show_gcal_auth"] = False
                        st.session_state["gcal_just_connected"] = True
                        st.rerun()
                    except Exception as auth_err:
                        st.error(f"❌ Failed to verify code: {auth_err}")
            except Exception as e:
                st.error(f"❌ Could not start Google authorization: {e}")
