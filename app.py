"""
SwimTrack Pro – Double Super-Admin Edition (V28)
Main Streamlit application entry point.
"""

import streamlit as st
import sys
import os

# ─── Path setup ───────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

import db as database
from config import APP_NAME

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=APP_NAME,
    page_icon="🏊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": f"**{APP_NAME}** V28 – מערכת ניהול שיעורי שחייה"},
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown(
    """<style>
    /* RTL support */
    body, .stApp { direction: rtl; }
    .stTextInput > label, .stSelectbox > label,
    .stTextArea > label, .stNumberInput > label,
    .stDateInput > label, .stCheckbox > label,
    .stRadio > label, .stForm > label { direction: rtl; text-align: right; }

    /* Sidebar styling */
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%); }
    [data-testid="stSidebar"] * { color: #e0e0e0 !important; }
    [data-testid="stSidebar"] .stButton > button {
        background: transparent; border: 1px solid #4ECDC433;
        color: #e0e0e0 !important; width: 100%; text-align: right;
        padding: 8px 12px; margin: 2px 0; border-radius: 8px;
        transition: all 0.2s;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: #4ECDC422; border-color: #4ECDC4;
    }

    /* Active nav item */
    .nav-active > button {
        background: #4ECDC433 !important; border-color: #4ECDC4 !important;
        font-weight: bold !important;
    }

    /* Cards */
    .metric-card { border-radius: 12px; padding: 16px; margin: 4px; }

    /* Forms RTL */
    .stForm { direction: rtl; }

    /* Dataframe RTL */
    [data-testid="stDataFrame"] { direction: rtl; }

    /* Hide Streamlit branding */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }

    /* Chat bubbles */
    .chat-bubble { border-radius: 10px; padding: 8px 12px; margin: 4px 0; }
    </style>""",
    unsafe_allow_html=True,
)

# ─── DB init ──────────────────────────────────────────────────────────────────
@st.cache_resource
def get_connection():
    database.init_db()
    return database.get_conn()

conn = get_connection()

# ─── Session state defaults ───────────────────────────────────────────────────
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_name" not in st.session_state:
    st.session_state.user_name = None
if "user_role" not in st.session_state:
    st.session_state.user_role = None
if "first_login" not in st.session_state:
    st.session_state.first_login = False
if "page" not in st.session_state:
    st.session_state.page = "dashboard"

# ─── Auth gate ────────────────────────────────────────────────────────────────
if not st.session_state.user_id:
    from modules.auth_ui import render_login_page
    render_login_page(conn)
    st.stop()

# ─── First-login tutorial ─────────────────────────────────────────────────────
if st.session_state.first_login:
    from modules.auth_ui import render_quick_start
    render_quick_start(conn)
    st.stop()

# ─── Navigation config ────────────────────────────────────────────────────────
ROLE_LABELS = {"super_admin": "סופר-מנהל 👑", "manager": "מנהל 🏅", "instructor": "מדריך 🏊"}

NAV_ITEMS = [
    ("dashboard",   "🏠 לוח בקרה"),
    ("groups",      "👥 קבוצות"),
    ("students",    "🎓 תלמידים"),
    ("attendance",  "✅ נוכחות"),
    ("syllabus",    "📚 סילבוס"),
    ("chat",        "💬 צ'אט"),
    ("shop",        "🛒 חנות"),
    ("inventory",   "📦 מלאי"),
    ("reports",     "📊 דוחות"),
    ("signatures",  "✍️ חתימות"),
    ("clock",       "⏱️ שעון"),
]

# Super-admin only pages
SUPER_ADMIN_PAGES = {}

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    # Logo / title
    st.markdown(
        """<div style='text-align:center;padding:16px 0 8px'>
            <div style='font-size:2.5rem'>🏊</div>
            <div style='font-size:1.3rem;font-weight:bold;color:#4ECDC4'>SwimTrack Pro</div>
            <div style='font-size:0.75rem;color:#888'>V28</div>
        </div>""",
        unsafe_allow_html=True,
    )

    # User info
    role_display = ROLE_LABELS.get(st.session_state.user_role, st.session_state.user_role)
    st.markdown(
        f"""<div style='background:#ffffff11;border-radius:8px;padding:10px 12px;margin:8px 0'>
            <div style='font-weight:bold;font-size:0.95rem'>{st.session_state.user_name}</div>
            <div style='font-size:0.8rem;color:#aaa'>{role_display}</div>
        </div>""",
        unsafe_allow_html=True,
    )

    # Unread badge
    unread = database.get_unread_count(conn, st.session_state.user_id)
    alerts = database.get_alerts(conn, unacknowledged_only=True)
    if unread or (alerts and st.session_state.user_role == "super_admin"):
        badges = []
        if unread:
            badges.append(f"💬 {unread}")
        if alerts and st.session_state.user_role == "super_admin":
            badges.append(f"🚨 {len(alerts)}")
        st.markdown(
            f"<div style='text-align:center;color:#FF6B6B;font-size:0.85rem'>"
            + "  ".join(badges) + "</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # Navigation
    for page_id, label in NAV_ITEMS:
        is_active = st.session_state.page == page_id
        container = st.container()
        with container:
            if is_active:
                st.markdown(
                    f"<div style='background:#4ECDC422;border:1px solid #4ECDC4;border-radius:8px;"
                    f"padding:8px 12px;margin:2px 0;color:#4ECDC4;font-weight:bold'>{label}</div>",
                    unsafe_allow_html=True,
                )
            else:
                if st.button(label, key=f"nav_{page_id}", use_container_width=True):
                    st.session_state.page = page_id
                    st.rerun()

    st.divider()

    # Data cleanup (super admin)
    if st.session_state.user_role == "super_admin":
        if st.button("🧹 ניקוי נתונים ישנים"):
            database.delete_old_student_data(conn)
            st.success("ניקוי בוצע!")

    # Logout
    if st.button("🚪 התנתק", use_container_width=True):
        for key in ["user_id", "user_name", "user_role", "first_login", "page"]:
            st.session_state.pop(key, None)
        st.rerun()

    # Global search shortcut
    st.divider()
    search_query = st.text_input("🔍 חיפוש מהיר", placeholder="שם / צבע / טלפון...")
    if search_query:
        results = database.search_students(conn, search_query)
        if results:
            st.caption(f"נמצאו {len(results)} תלמידים:")
            for r in results[:5]:
                st.caption(f"• {r['name']} ({r['level_color']})")
            if len(results) > 5:
                st.caption(f"+ {len(results)-5} נוספים")
            if st.button("צפה בכל התוצאות"):
                st.session_state.page = "students"
                st.rerun()
        else:
            st.caption("לא נמצאו תוצאות")

# ─── Main content router ──────────────────────────────────────────────────────
page = st.session_state.page

if page == "dashboard":
    from modules.dashboard import render
    render(conn)

elif page == "groups":
    from modules.groups import render
    render(conn)

elif page == "students":
    from modules.students import render
    render(conn)

elif page == "attendance":
    from modules.attendance import render
    render(conn)

elif page == "syllabus":
    from modules.syllabus import render
    render(conn)

elif page == "chat":
    from modules.chat import render
    render(conn)

elif page == "shop":
    from modules.shop import render
    render(conn)

elif page == "inventory":
    from modules.inventory import render
    render(conn)

elif page == "reports":
    from modules.reports import render
    render(conn)

elif page == "signatures":
    from modules.signatures import render
    render(conn)

elif page == "clock":
    from modules.clock import render
    render(conn)

elif page == "alerts":
    from modules.chat import _render_alerts
    st.markdown("## 🚨 התראות מערכת")
    _render_alerts(conn)

else:
    st.error(f"עמוד לא ידוע: {page}")

# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown(
    """<div style='position:fixed;bottom:0;left:0;right:0;background:#1a1a2e;
        padding:6px;text-align:center;font-size:0.75rem;color:#555;z-index:999'>
        SwimTrack Pro V28 © 2024 | מערכת ניהול שיעורי שחייה מקצועית
    </div>""",
    unsafe_allow_html=True,
)
