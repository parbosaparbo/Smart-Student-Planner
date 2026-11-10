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
        # Import streamlit_calendar at module level to catch ImportError cleanly
        _calendar_available = False
        _calendar_import_error = None
        try:
            from streamlit_calendar import calendar as st_calendar
            _calendar_available = True
        except ImportError as ie:
            _calendar_import_error = ie
        except Exception as ie:
            _calendar_import_error = ie

        if not _calendar_available:
            st.warning(
                f"📅 Calendar view requires the `streamlit-calendar` package.\n\n"
                f"**Install it with:** `pip install streamlit-calendar`\n\n"
                f"Error: `{_calendar_import_error}`"
            )
        elif not calendar_events:
            st.info("📅 No schedule events to display. Generate a study schedule first!")
        else:
            try:
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
                st_calendar(events=calendar_events, options=cal_options, custom_css="""
                    .fc-event { border-radius: 4px; font-size: 0.85rem; padding: 2px 4px; }
                """)
            except Exception as e:
                st.error(f"📅 Calendar rendering error: `{type(e).__name__}: {e}`")
                st.info("Switching to list view as fallback...")
                # Fallback: show events as a simple table
                import pandas as _pd
                if calendar_events:
                    df = _pd.DataFrame([
                        {
                            "Date": ev.get("start", "")[:10],
                            "Time": ev.get("start", "")[11:16] if "T" in ev.get("start", "") else "All Day",
                            "Event": ev.get("title", ""),
                        }
                        for ev in calendar_events
                    ])
                    st.dataframe(df, use_container_width=True, hide_index=True)

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

    st.info(
        "💡 **Need to adapt or reschedule?** If you score <70% on a quiz or want extra practice on any topic, "
        "head over to **Page 4 (📊 Weak Spot Analyzer)** to automatically insert evidence-based spaced revision slots "
        "(**Round 1: 1–2 days**, **Round 2: 4–6 days**) directly into your calendar without disturbing completed sessions!"
    )

    # ── Google Calendar Sync Section ────────────────────────────────────────────
    st.divider()
    st.subheader("📅 Google Calendar & Schedule Export")

    student_key = st.session_state.get("student_profile", {}).get("student_name", "Student")
    student_name = student_key

    # Pre-generate .ics calendar data for offline fallback
    ics_content = gcal.export_schedule_to_ics(schedule, student_name=student_name)

    if not gcal.is_configured():
        st.warning("⚠️ Google Calendar Developer credentials not yet configured.")
        with st.expander("🛠️ Developer One-Time Setup Guide (Google Cloud & OAuth)", expanded=True):
            st.markdown("""
            **Developer Instructions (Configure Once):**
            1. Open [Google Cloud Console](https://console.cloud.google.com/) and create a project (`studymind-ai`).
            2. Enable the **Google Calendar API** (`APIs & Services` → `Library`).
            3. Configure **OAuth Consent Screen**:
               - User Type: **External**
               - Scopes: `openid`, `userinfo.email`, `https://www.googleapis.com/auth/calendar.events`
               - Test Users: Add student Gmail addresses for testing before public verification.
            4. Create **OAuth 2.0 Client ID** (Desktop / Web application).
            5. Download and save client JSON as `credentials.json` in the project root.
            """)
        st.download_button(
            label="📥 Download .ics Calendar File (Use Offline / Outlook / Apple / Google)",
            data=ics_content,
            file_name=f"studymind_schedule_{date.today().strftime('%Y%m%d')}.ics",
            mime="text/calendar",
            width="stretch"
        )
    elif gcal.is_connected(student_key):
        # ── Connected View ────────────────────────────────────────────────────────
        email = gcal.get_connected_account_email(student_key)
        account_label = f"**{email}**" if email and "@" in email else "your Google Account"
        
        st.markdown(f"""
        <div style='background:linear-gradient(135deg,{COLORS["success"]}15,{COLORS["card_bg"]});
                    border-left:4px solid {COLORS["success"]}; padding:1.2rem; border-radius:10px; margin-bottom:1rem;'>
          <h4 style='margin:0; color:{COLORS["success"]};'>✅ Google Calendar Connected</h4>
          <p style='margin:0.2rem 0 0; color:white;'>
            Linked to {account_label} · 🔔 Native 10-minute reminders active for Android, iPhone &amp; Desktop.
          </p>
        </div>
        """, unsafe_allow_html=True)

        col_act1, col_act2, col_act3 = st.columns([1.5, 1.5, 1])
        with col_act1:
            if st.button("⚡ Sync Now (Google Calendar)", type="primary", width="stretch", key="gcal_sync_now"):
                with st.spinner("Syncing schedule with Google Calendar (updating existing & removing obsolete slots)..."):
                    try:
                        result = gcal.sync_schedule_to_calendar(schedule, student_key, student_name)
                        st.session_state["gcal_event_map"] = result
                        save_persistent_state(st.session_state)
                        
                        msg = f"✅ Synced! **{result['created']}** created, **{result['updated']}** updated, **{result['deleted']}** obsolete removed."
                        st.success(msg)
                        if result["errors"]:
                            st.warning(f"⚠️ {len(result['errors'])} error(s) during sync: " + "; ".join(result["errors"][:3]))
                        else:
                            st.balloons()
                    except ValueError as ve:
                        st.error(f"❌ {ve}")
                    except Exception as sync_err:
                        st.error(f"❌ Google Calendar sync error: {sync_err}")

        with col_act2:
            st.download_button(
                label="📥 Download .ics File",
                data=ics_content,
                file_name=f"studymind_schedule_{date.today().strftime('%Y%m%d')}.ics",
                mime="text/calendar",
                width="stretch",
                key="dl_ics_connected"
            )

        with col_act3:
            if st.button("🔌 Disconnect", width="stretch", key="gcal_disconnect"):
                gcal.delete_token(student_key)
                st.toast("Google Calendar disconnected.", icon="🔌")
                st.rerun()

        # Show Last Sync Metrics
        last_sync = st.session_state.get("gcal_event_map")
        if last_sync and isinstance(last_sync, dict):
            with st.expander("📊 Google Calendar Sync Details", expanded=False):
                s1, s2, s3, s4, s5 = st.columns(5)
                s1.metric("Active Sessions", last_sync.get("total_blocks", 0))
                s2.metric("Created", last_sync.get("created", 0))
                s3.metric("Updated", last_sync.get("updated", 0))
                s4.metric("Obsolete Removed", last_sync.get("deleted", 0))
                s5.metric("Rest Days Skipped", last_sync.get("skipped", 0))
                if last_sync.get("last_synced_at"):
                    st.caption(f"Last synchronized: `{last_sync.get('last_synced_at')[:19].replace('T', ' ')}`")

        if st.button("🗑️ Remove All StudyMind Events from Calendar", key="gcal_clean_all", help="Deletes only events created by StudyMind. Personal events are never touched."):
            with st.spinner("Cleaning StudyMind events from Google Calendar..."):
                try:
                    count = gcal.delete_all_synced_events(student_key)
                    st.success(f"✅ Removed {count} StudyMind events from your calendar.")
                except Exception as del_err:
                    st.error(f"❌ Could not remove events: {del_err}")

    else:
        # ── Disconnected Student View ─────────────────────────────────────────────
        st.markdown(f"""
        <div style='background:{COLORS["card_bg"]}; border:1px solid rgba(255,255,255,0.08);
                    border-radius:10px; padding:1.2rem; margin-bottom:1rem;'>
          <h4 style='margin:0 0 0.4rem; color:white;'>Synchronize with your Google Calendar</h4>
          <p style='color:{COLORS["text_muted"]}; margin:0; font-size:0.92rem;'>
            Connect your Gmail to auto-schedule study blocks &amp; spaced revisions with <b>10-minute popups and email alerts</b> that notify you on Android, iPhone &amp; laptop even when offline.
          </p>
        </div>
        """, unsafe_allow_html=True)

        c_btn1, c_btn2, c_btn3 = st.columns([1.5, 1.2, 1.3])
        with c_btn1:
            if st.button("🔗 Connect Google Calendar (Instant)", type="primary", width="stretch", key="gcal_connect_local"):
                with st.spinner("Opening Google sign-in consent screen in your browser..."):
                    success, msg = gcal.connect_via_local_server(student_key)
                    if success:
                        st.session_state["gcal_just_connected"] = True
                        st.rerun()
                    else:
                        st.error(f"❌ Connection error: {msg}")

        with c_btn2:
            if st.button("🌐 Browser Link / Enter Code", width="stretch", key="gcal_toggle_manual"):
                st.session_state["show_gcal_auth"] = not st.session_state.get("show_gcal_auth", False)

        with c_btn3:
            st.download_button(
                label="📥 Download .ics File",
                data=ics_content,
                file_name=f"studymind_schedule_{date.today().strftime('%Y%m%d')}.ics",
                mime="text/calendar",
                width="stretch",
                key="dl_ics_disconnected",
                help="Offline calendar export compatible with Google Calendar, Apple Calendar, and Outlook."
            )

        if st.session_state.get("show_gcal_auth", False):
            try:
                auth_url, state = gcal.build_auth_url(student_key)
                st.markdown(
                    f"""
                    <div style='background:{COLORS["card_bg"]}; border-radius:10px; padding:1.2rem; border:1px solid rgba(255,255,255,0.1); margin:1rem 0;'>
                      <h4 style='margin:0 0 0.5rem;'>Sign in with Google</h4>
                      <p style='color:{COLORS["text_muted"]}; font-size:0.9rem;'>
                        Click the button below to sign in with your Google account. If your browser redirects to localhost, copy the code from the address bar and paste it below.
                      </p>
                      <a href='{auth_url}' target='_blank' style='display:inline-block; padding:0.6rem 1.5rem; 
                         background:{COLORS["primary"]}; color:white; border-radius:8px; 
                         text-decoration:none; font-weight:600; margin-bottom:1rem;'>🔐 Open Google Sign-In Screen ↗</a>
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

        # Developer Diagnostics (tucked into clean expander)
        dev_stat = gcal.get_developer_oauth_status()
        with st.expander("🛠️ Developer Information & OAuth Details", expanded=False):
            st.caption(f"**Client Type:** `{dev_stat.get('client_type')}` · **Client ID:** `{dev_stat.get('client_id_prefix')}`")
            st.caption(f"**Redirect URIs:** `{', '.join(dev_stat.get('redirect_uris', []))}`")
            st.caption(f"**Required Scopes:** `{', '.join(dev_stat.get('scopes', []))}`")
