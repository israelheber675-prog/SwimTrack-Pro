"""SwimTrack Pro – Authentication UI"""

import streamlit as st
from config import QUICK_START_GUIDE
import db


def render_login_page(conn):
    st.markdown(
        """<div style='text-align:center;padding:20px 0'>
            <div style='font-size:3rem'>🏊</div>
            <div style='font-size:1.8rem;font-weight:bold'>SwimTrack Pro</div>
            <div style='color:#888'>מערכת ניהול שיעורי שחייה</div>
        </div>""",
        unsafe_allow_html=True,
    )

    tab_login, tab_register = st.tabs(["🔑 התחברות", "📝 הרשמה"])
    with tab_login:
        _render_login(conn)
    with tab_register:
        _render_register(conn)


# ─── Login ────────────────────────────────────────────────────────────────────

def _render_login(conn):
    with st.form("login_form"):
        identifier = st.text_input("אימייל / טלפון", placeholder="user@example.com")
        password = st.text_input("סיסמה", type="password")
        submitted = st.form_submit_button("🔑 התחבר", use_container_width=True, type="primary")

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

        st.session_state.user_id    = user["id"]
        st.session_state.user_name  = user["name"]
        st.session_state.user_role  = user["role"]
        st.session_state.first_login = not bool(user["first_login_done"])
        st.session_state.page       = "dashboard"
        st.rerun()


# ─── Register ─────────────────────────────────────────────────────────────────

def _render_register(conn):
    user_count = db.count_users(conn)

    if user_count < 2:
        st.info(
            "🌟 אתה מבין הראשונים! שני המשתמשים הראשונים יקבלו אוטומטית "
            "הרשאות **סופר-מנהל**, ללא קשר לתפקיד שתבחר."
        )

    with st.form("register_form"):
        col1, col2 = st.columns(2)
        with col1:
            name  = st.text_input("שם מלא *", placeholder="ישראל ישראלי")
            email = st.text_input("אימייל", placeholder="user@example.com")
        with col2:
            phone     = st.text_input("טלפון", placeholder="050-0000000")
            password  = st.text_input("סיסמה *", type="password")
        password2 = st.text_input("אימות סיסמה *", type="password")

        st.divider()

        # ── Role selection – always visible ───────────────────────────────────
        st.markdown("**בחר תפקיד:**")
        role = st.radio(
            "תפקיד",
            ["manager", "instructor"],
            format_func=lambda r: "🏅 מנהל – אחראי על קבוצות ומדריכים"
                                   if r == "manager"
                                   else "🏊 מדריך – עובד עם תלמידים בבריכה",
            horizontal=False,
            label_visibility="collapsed",
        )

        # ── Manager selection for instructors ─────────────────────────────────
        belongs_to_manager_id = None
        if role == "instructor":
            managers    = db.get_users_by_role(conn, "manager")
            super_admins = db.get_users_by_role(conn, "super_admin")
            all_managers = list(managers) + list(super_admins)
            if all_managers:
                mgr_map  = {f"{u['name']} ({'מנהל' if u['role']=='manager' else 'סופר-מנהל'})": u["id"]
                            for u in all_managers}
                mgr_opts = ["— לא נבחר עדיין —"] + list(mgr_map.keys())
                sel_mgr  = st.selectbox("📌 השתייך למנהל", mgr_opts)
                if sel_mgr != "— לא נבחר עדיין —":
                    belongs_to_manager_id = mgr_map[sel_mgr]
            else:
                st.caption("💡 טרם נרשמו מנהלים – תוכל לבחור מנהל מאוחר יותר מהפרופיל")

        submitted = st.form_submit_button("📝 הרשם", use_container_width=True, type="primary")

    if submitted:
        _do_register(conn, name, email, phone, password, password2, role, belongs_to_manager_id)


def _do_register(conn, name, email, phone, password, password2, role, belongs_to_manager_id):
    errors = []
    if not name.strip():
        errors.append("שם מלא הוא שדה חובה")
    if not email.strip() and not phone.strip():
        errors.append("יש לספק אימייל או טלפון לצורך התחברות")
    if not password:
        errors.append("סיסמה היא שדה חובה")
    elif len(password) < 6:
        errors.append("סיסמה חייבת להכיל לפחות 6 תווים")
    if password != password2:
        errors.append("הסיסמאות אינן תואמות")

    if errors:
        for e in errors:
            st.error(e)
        return

    try:
        user_id = db.create_user(
            conn, name.strip(),
            email.strip() or None,
            phone.strip() or None,
            password,
            role,
            belongs_to_manager_id,
        )
        user = db.get_user(conn, user_id)
        actual_role = user["role"]

        if actual_role == "super_admin":
            st.balloons()
            st.success("🎉 נרשמת כ**סופר-מנהל**! ברוך הבא למערכת.")
        else:
            st.success("✅ נרשמת בהצלחה!")

        st.session_state.user_id    = user_id
        st.session_state.user_name  = name.strip()
        st.session_state.user_role  = actual_role
        st.session_state.first_login = True
        st.session_state.page       = "dashboard"
        st.rerun()

    except Exception as e:
        if "UNIQUE" in str(e):
            st.error("אימייל או טלפון כבר קיים במערכת")
        else:
            st.error(f"שגיאה בהרשמה: {e}")


# ─── Quick Start Guide ────────────────────────────────────────────────────────

ROLE_GUIDES = {
    "super_admin": """
### 👑 מדריך מהיר – סופר-מנהל

כסופר-מנהל יש לך גישה לכל המערכת:

| מסך | מה לעשות ראשון |
|-----|----------------|
| 👥 קבוצות | צור קבוצה ראשונה ושייך מנהל ומדריך |
| 🎓 תלמידים | הוסף תלמידים לקבוצה |
| 🛒 חנות | הוסף מוצרים לחנות |
| 📦 מלאי | הזן ציוד ראשוני |
| 💬 צ'אט | תקשר עם כל הצוות |
| 🚨 התראות | עקוב אחר הודעות חסומות ופעולות חריגות |

> **טיפ:** ניתן לחפש כל תלמיד בסרגל החיפוש השמאלי לפי שם, צבע רמה, או מספר טלפון.
""",
    "manager": """
### 🏅 מדריך מהיר – מנהל

| מסך | מה לעשות ראשון |
|-----|----------------|
| 👥 קבוצות | צור קבוצה ושייך לה מדריך |
| 🎓 תלמידים | הוסף תלמידים + טעינת קרדיטים |
| ✅ נוכחות | פתח שיעורים וסמן נוכחות |
| 💬 צ'אט | שלח פידבק למדריכים |
| 📊 דוחות | צור דוחות WhatsApp ב-6 שפות |
""",
    "instructor": """
### 🏊 מדריך מהיר – מדריך

| מסך | מה לעשות |
|-----|----------|
| ✅ נוכחות | פתח שיעור יומי + סמן נוכחות |
| 📚 סילבוס | עדכן התקדמות תלמידים לפי שלבים וצבעים |
| 🏊 נתיבים | שבץ תלמידים לנתיבים (רשימה / מפה גרפית) |
| ⏱️ שעון | לחץ "כניסה" בתחילת יום ו"יציאה" בסופו |
| 💬 צ'אט | תקשר עם המנהל שלך |

> **שים לב:** קרדיט מנוכה אוטומטית עם סימון "נוכח".
""",
}

def render_quick_start(conn):
    """Personalized first-login tutorial per role."""
    role = st.session_state.user_role
    name = st.session_state.user_name

    st.markdown(f"## 👋 ברוך הבא, {name}!")

    guide = ROLE_GUIDES.get(role, ROLE_GUIDES["instructor"])
    st.markdown(guide)

    st.divider()
    st.markdown(QUICK_START_GUIDE)

    if st.button("✅ הבנתי! קח אותי ללוח הבקרה", use_container_width=True, type="primary"):
        db.mark_first_login(conn, st.session_state.user_id)
        st.session_state.first_login = False
        st.rerun()
