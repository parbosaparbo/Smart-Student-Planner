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

          /* Prepend 🏠 to Dashboard in the sidebar navigation */
          [data-testid="stSidebarNav"] ul li:first-child a > span:first-child::before,
          [data-testid="stSidebarNav"] a[href$="/"] > span:first-child::before,
          [data-testid="stSidebarNav"] a[href$="/Dashboard"] > span:first-child::before {{
              content: "🏠\\00a0 ";
              font-style: normal;
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
        """, unsafe_allow_html=True)


def nav_to_dashboard():
    """Safely navigates to the main Dashboard."""
    st.switch_page("Dashboard.py")

