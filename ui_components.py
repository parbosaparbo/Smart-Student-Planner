"""
StudyMind AI — Shared UI Components
"""
import streamlit as st
from config import APP_TITLE, APP_ICON, APP_SUBTITLE, COLORS


def render_sidebar_header():
    """Renders the standard brand header at the top of the sidebar navbar."""
    with st.sidebar:
        st.markdown(f"""
        <style>
          /* Keep brand header at the top of sidebar, followed by navigation links */
          [data-testid="stSidebarContent"] {{
              display: flex !important;
              flex-direction: column !important;
          }}
          [data-testid="stSidebarUserContent"] {{
              order: 1 !important;
              padding-top: 0 !important;
          }}
          [data-testid="stSidebarNav"] {{
              order: 2 !important;
              margin-top: 0.25rem !important;
          }}


          /* Responsive main container starting right after sidebar */
          .main .block-container {{
              max-width: 1280px;
              padding-top: 1.8rem;
              padding-bottom: 3rem;
              padding-left: 2.5rem;
              padding-right: 2.5rem;
          }}
          @media (max-width: 992px) {{
              .main .block-container {{
                  padding-left: 1.5rem;
                  padding-right: 1.5rem;
                  padding-top: 1.2rem;
              }}
          }}
          @media (max-width: 576px) {{
              .main .block-container {{
                  padding-left: 1rem;
                  padding-right: 1rem;
                  padding-top: 1rem;
              }}
          }}
        </style>
        <div style='display: flex; flex-direction: row; align-items: center; gap: 12px; padding: 0.4rem 0 0.8rem 0; margin-bottom: 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.08);'>
          <span style='font-size: 2rem; line-height: 1; display: inline-flex; align-items: center; justify-content: center;'>{APP_ICON}</span>
          <div style='display: flex; flex-direction: column; justify-content: center; line-height: 1.2;'>
            <div style='font-size: 1.25rem; font-weight: 800; color: {COLORS["primary"]}; line-height: 1.2; letter-spacing: -0.01em;'>{APP_TITLE}</div>
            <div style='color: {COLORS["text_muted"]}; font-size: 0.75rem; line-height: 1.1;'>{APP_SUBTITLE}</div>
          </div>
        </div>
        <img src="x" onerror="
          (function() {{
            function updateNav() {{
              var links = document.querySelectorAll('[data-testid=\\'stSidebarNavLink\\'], section[data-testid=\\'stSidebar\\'] a');
              links.forEach(function(el) {{
                var spans = el.querySelectorAll('span');
                spans.forEach(function(s) {{
                  if (s && s.innerText && s.innerText.trim() === 'Dashboard' && s.innerHTML.indexOf('🏠') === -1) {{
                    s.innerHTML = '🏠&nbsp;&nbsp;Dashboard';
                  }}
                }});
              }});
            }}
            updateNav();
            if (!window.__smNavObserver) {{
              window.__smNavObserver = new MutationObserver(updateNav);
              window.__smNavObserver.observe(document.body, {{ childList: true, subtree: true }});
            }}
          }})();
        " style="display:none;" />
        """, unsafe_allow_html=True)


def render_gcal_sidebar_status():
    """Show Google Calendar connection status in the sidebar."""
    try:
        import google_calendar as gcal
        if not gcal.is_configured():
            return
        student = st.session_state.get("student_profile", {})
        student_key = student.get("student_name", "")
        with st.sidebar:
            if gcal.is_connected(student_key):
                email = gcal.get_connected_account_email(student_key)
                if email and "@" in email:
                    st.caption(f"📅 Google Calendar: ✅ Connected ({email})")
                else:
                    st.caption("📅 Google Calendar: ✅ Connected")
            else:
                st.caption("📅 Google Calendar: 🔗 Not connected")
    except Exception:
        pass


def nav_to_dashboard():
    """Safely navigates to the main Dashboard."""
    st.switch_page("Dashboard.py")

