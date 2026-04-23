"""SwimTrack Pro – Authentication UI"""

import streamlit as st
from config import QUICK_START_GUIDE
import db


def render_login_page(conn):
    st.markdown("## 🏊 SwimTrack Pro")
    st.markdown("##### מערכת ניהול שיעורי שחייה")

    tab_login, tab_register = st.tabs(["🔑 התחברות", "📝 הרשמה"])

    with tab_login:
        _render_login(conn)

    with tab_register:
        _render_register(conn)


def _render_login(conn):
    with st.form("login_form"):
        identifier = st.text_input("אימייל / טלפון", placeholder="user@example.com")
        password = st.text_input("סיסמה", type="password")
        submitted = st.form_submit_button("התחבר", use_container_width=True)

    if submitted:
        if not identifier or not password:
            st.error("נא למלא את כל השדות")
            return
        user = db.get_user_by_login(conn, identifier)
        if not user:
            st.error("משתמש לא נמצא")
            return
        if not db.verify_password(password, user["password_hash"], user["salt"]):
            st.error("סיסמה שגויה")
            return

        st.session_state.user_id = user["id"]
        st.session_state.user_name = user["name"]
        st.session_state.user_role = user["role"]
        st.session_state.first_login = not bool(user["first_login_done"])
        st.session_state.page = "dashboard"
        st.rerun()


def _render_register(conn):
    user_count = db.count_users(conn)
    if user_count < 2:
        st.info("🌟 אתה מבין הראשונים! שני המשתמשים הראשונים יקבלו אוטומטית הרשאות **סופר-מנהל**.")
    else:
        st.caption("המשתמשים הראשונים כבר נרשמו. בחר תפקיד:")

    with st.form("register_form"):
        name = st.text_input("שם מלא *", placeholder="ישראל ישראלי")
        email = st.text_input("אימייל", placeholder="user@example.com")
        phone = st.text_input("טלפון", placeholder="050-0000000")
        password = st.text_input("סיסמה *", type="password")
        password2 = st.text_input("אימות סיסמה *", type="password")

        if user_count >= 2:
            role = st.radio("תפקיד", ["manager", "instructor"],
                            format_func=lambda r: "מנהל" if r == "manager" else "מדריך")
        else:
            role = "super_admin"

        submitted = st.form_submit_button("הרשם", use_container_width=True)

    if submitted:
        errors = []
        if not name:
            errors.append("שם מלא הוא שדה חובה")
        if not email and not phone:
            errors.append("יש לספק אימייל או טלפון לצורך התחברות")
        if not password:
            errors.append("סיסמה היא שדה חובה")
        if password != password2:
            errors.append("הסיסמאות אינן תואמות")
        if len(password) < 6:
            errors.append("סיסמה חייבת להכיל לפחות 6 תווים")

        if errors:
            for e in errors:
                st.error(e)
            return

        try:
            user_id = db.create_user(conn, name, email, phone, password, role)
            user = db.get_user(conn, user_id)
            st.session_state.user_id = user_id
            st.session_state.user_name = name
            st.session_state.user_role = user["role"]
            st.session_state.first_login = True
            st.session_state.page = "dashboard"
            st.success("נרשמת בהצלחה! מתחבר...")
            st.rerun()
        except Exception as e:
            if "UNIQUE" in str(e):
                st.error("אימייל או טלפון כבר קיים במערכת")
            else:
                st.error(f"שגיאה בהרשמה: {e}")


def render_quick_start(conn):
    """Show first-login tutorial."""
    st.markdown(QUICK_START_GUIDE)
    if st.button("✅ הבנתי! קח אותי ללוח הבקרה", use_container_width=True, type="primary"):
        db.mark_first_login(conn, st.session_state.user_id)
        st.session_state.first_login = False
        st.rerun()
