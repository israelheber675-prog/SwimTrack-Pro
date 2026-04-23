"""SwimTrack Pro – Safe Hierarchical Chat + Feedback Notes"""

import streamlit as st
import re
from config import LANGUAGE_BLACKLIST
import db


def _check_message(message: str) -> tuple[bool, str]:
    """Returns (is_blocked, reason). No media in text chat."""
    lower = message.lower()
    for word in LANGUAGE_BLACKLIST:
        pattern = r'\b' + re.escape(word.lower()) + r'\b'
        if re.search(pattern, lower):
            return True, f"תוכן פוגעני: '{word}'"
    return False, ""


def _allowed_contacts(conn, user_id: int, role: str):
    """Return list of users this role may chat with."""
    if role == "super_admin":
        return db.get_all_users(conn)
    elif role == "manager":
        super_admins = db.get_users_by_role(conn, "super_admin")
        return list(super_admins)
    elif role == "instructor":
        managers = db.get_users_by_role(conn, "manager")
        super_admins = db.get_users_by_role(conn, "super_admin")
        return list(managers) + list(super_admins)
    return []


def render(conn):
    st.markdown("## 💬 תקשורת פנימית")
    role = st.session_state.user_role
    user_id = st.session_state.user_id

    unread = db.get_unread_count(conn, user_id)
    if unread:
        st.info(f"📬 יש לך {unread} הודעות שלא נקראו")

    tab_chat, tab_feedback, tab_alerts = st.tabs(["💬 צ'אט", "📌 פידבק מנהל", "🚨 התראות מערכת"])

    with tab_chat:
        _render_chat(conn, user_id, role)

    with tab_feedback:
        _render_feedback(conn, user_id, role)

    with tab_alerts:
        if role == "super_admin":
            _render_alerts(conn)
        else:
            st.info("התראות מערכת זמינות לסופר-מנהלים בלבד")


def _render_chat(conn, user_id, role):
    contacts = _allowed_contacts(conn, user_id, role)
    contacts = [u for u in contacts if u["id"] != user_id]

    if not contacts:
        st.info("אין אנשי קשר זמינים לתפקידך כרגע")
        return

    contact_map = {u["name"]: u for u in contacts}
    role_labels = {"super_admin": "סופר-מנהל", "manager": "מנהל", "instructor": "מדריך"}

    sel_name = st.selectbox(
        "שוחח עם",
        list(contact_map.keys()),
        format_func=lambda n: f"{n}  ({role_labels.get(contact_map[n]['role'], '')})",
    )
    sel_user = contact_map[sel_name]
    db.mark_messages_read(conn, user_id, sel_user["id"])

    # Show conversation
    messages = db.get_conversation(conn, user_id, sel_user["id"])
    st.markdown(f"#### שיחה עם {sel_name}")

    chat_container = st.container()
    with chat_container:
        if messages:
            for m in messages:
                is_me = m["sender_id"] == user_id
                align = "flex-end" if is_me else "flex-start"
                bg = "#DCF8C6" if is_me else "#FFFFFF"
                border = "#A8E6B0" if is_me else "#DDDDDD"
                sender_label = "אתה" if is_me else m["sender_name"]
                time_str = m["sent_at"][11:16] if m["sent_at"] else ""
                st.markdown(
                    f"""<div style='display:flex;justify-content:{align};margin:4px 0'>
                        <div style='background:{bg};border:1px solid {border};border-radius:10px;
                            padding:8px 12px;max-width:70%;box-shadow:0 1px 2px rgba(0,0,0,0.1)'>
                            <div style='font-size:0.75rem;color:#888;margin-bottom:2px'>{sender_label}</div>
                            <div>{m['message']}</div>
                            <div style='font-size:0.7rem;color:#aaa;text-align:right;margin-top:4px'>{time_str}</div>
                        </div>
                    </div>""",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("אין הודעות עדיין. שלח הודעה ראשונה!")

    # Compose
    st.divider()
    with st.form("chat_form", clear_on_submit=True):
        col1, col2 = st.columns([5, 1])
        with col1:
            new_msg = st.text_input(
                "הודעה",
                placeholder="כתוב הודעה... (לא ניתן לשלוח תמונות/סרטונים)",
                label_visibility="collapsed",
            )
        with col2:
            send = st.form_submit_button("שלח ➤", use_container_width=True)

    if send and new_msg.strip():
        blocked, reason = _check_message(new_msg.strip())
        if blocked:
            st.error(f"🚫 ההודעה נחסמה: {reason}")
            # Save blocked message + alert
            db.send_message(conn, user_id, sel_user["id"], new_msg.strip(), blocked=True, block_reason=reason)
            sender = db.get_user(conn, user_id)
            db.create_alert(
                conn,
                "blocked_message",
                f"הודעה נחסמה מ-{sender['name']}: \"{new_msg.strip()[:80]}\" | סיבה: {reason}",
                user_id,
            )
        else:
            db.send_message(conn, user_id, sel_user["id"], new_msg.strip())
            st.rerun()

    st.caption("⚠️ לא ניתן לשלוח מדיה. כל ההודעות מנוטרות אוטומטית.")


def _render_feedback(conn, user_id, role):
    if role in ("super_admin", "manager"):
        _render_send_feedback(conn, user_id, role)
    _render_received_feedback(conn, user_id)


def _render_send_feedback(conn, from_user_id, role):
    st.markdown("#### 📤 שלח פידבק / מחמאה למדריך")
    instructors = db.get_users_by_role(conn, "instructor")
    if not instructors:
        st.info("אין מדריכים רשומים")
        return

    inst_map = {u["name"]: u["id"] for u in instructors}
    sel_inst = st.selectbox("מדריך", list(inst_map.keys()), key="fb_inst")
    note_text = st.text_area("טקסט הפידבק / מחמאה", placeholder="כתוב כאן...", height=100)

    if st.button("📨 שלח פידבק", type="primary") and note_text.strip():
        db.add_feedback(conn, from_user_id, inst_map[sel_inst], note_text.strip())
        st.success("✅ הפידבק נשלח!")
        st.rerun()


def _render_received_feedback(conn, user_id):
    st.markdown("#### 📥 פידבקים שקיבלתי")
    feedbacks = db.get_feedback_for_user(conn, user_id)
    if not feedbacks:
        st.info("לא קיבלת פידבקים עדיין")
        return
    for f in feedbacks:
        st.markdown(
            f"""<div style='background:#FFF9C4;border-left:4px solid #FFD700;
                padding:10px;border-radius:6px;margin-bottom:8px'>
                <b>{f['from_name']}</b> • {f['created_at'][:10]}<br>{f['note']}
            </div>""",
            unsafe_allow_html=True,
        )


def _render_alerts(conn):
    st.markdown("#### 🚨 התראות מערכת")
    alerts = db.get_alerts(conn, unacknowledged_only=False)
    if not alerts:
        st.success("אין התראות פעילות")
        return

    unacked = [a for a in alerts if not a["acknowledged"]]
    acked = [a for a in alerts if a["acknowledged"]]

    if unacked:
        st.markdown(f"**לא נקראו ({len(unacked)})**")
        for a in unacked:
            col1, col2 = st.columns([4, 1])
            with col1:
                st.error(f"🚨 [{a['alert_type']}]  {a['created_at'][:16]}  —  {a['message']}")
            with col2:
                if st.button("✅ נקרא", key=f"ack_{a['id']}"):
                    db.acknowledge_alert(conn, a["id"])
                    st.rerun()

    if acked:
        with st.expander(f"היסטוריה ({len(acked)} התראות)"):
            for a in acked:
                st.caption(f"✅ [{a['alert_type']}]  {a['created_at'][:16]}  —  {a['message']}")
