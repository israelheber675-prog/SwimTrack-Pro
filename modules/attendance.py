"""SwimTrack Pro – Attendance & Credits + Lane Mapping"""

import streamlit as st
import pandas as pd
from datetime import date
import db


def render(conn):
    st.markdown("## ✅ נוכחות וקרדיטים")

    tab_att, tab_lanes, tab_credits = st.tabs(
        ["📝 סימון נוכחות", "🏊 שיבוץ נתיבים", "💳 ניהול קרדיטים"]
    )
    with tab_att:
        _render_attendance(conn)
    with tab_lanes:
        _render_lanes(conn)
    with tab_credits:
        _render_credits(conn)


# ─── Attendance ───────────────────────────────────────────────────────────────

def _render_attendance(conn):
    groups = db.get_groups(conn)
    if not groups:
        st.info("אין קבוצות פעילות")
        return

    group_map = {g["name"]: g for g in groups}
    sel_group_name = st.selectbox("בחר קבוצה", list(group_map.keys()))
    group = group_map[sel_group_name]

    col1, col2 = st.columns([2, 1])
    with col1:
        session_date = st.date_input("תאריך שיעור", value=date.today())
    with col2:
        notes = st.text_input("הערות לשיעור", placeholder="אופציונלי")

    # Get or create session
    existing_session = conn.execute(
        "SELECT * FROM sessions WHERE group_id=? AND session_date=?",
        (group["id"], session_date.isoformat()),
    ).fetchone()

    if existing_session:
        session_id = existing_session["id"]
        st.info(f"📅 שיעור קיים בתאריך זה (ID: {session_id})")
    else:
        if st.button("🆕 פתח שיעור לתאריך זה", type="primary"):
            session_id = db.create_session(
                conn, group["id"], session_date.isoformat(),
                st.session_state.user_id, notes,
            )
            st.success(f"שיעור נפתח (ID: {session_id})")
            st.rerun()
        return

    # Attendance table
    students = db.get_students(conn, group["id"])
    if not students:
        st.info("אין תלמידים בקבוצה זו")
        return

    att_records = {a["student_id"]: a for a in db.get_attendance(conn, session_id)}

    st.markdown("### 📋 רשימת נוכחות")
    is_private = len(students) == 1  # Private lesson

    for s in students:
        att = att_records.get(s["id"])
        is_present = bool(att and att["present"])
        credits_left = s["credits"]

        col_name, col_cred, col_chk = st.columns([3, 1, 1])
        with col_name:
            st.write(f"**{s['name']}**  —  רמה: {s['level_color']}")
        with col_cred:
            if credits_left <= 0:
                st.error(f"💳 {credits_left:.0f}")
                if is_private:
                    st.warning("⚠️ תלמיד בגירעון!")
            elif credits_left <= 2:
                st.warning(f"💳 {credits_left:.0f}")
            else:
                st.success(f"💳 {credits_left:.0f}")
        with col_chk:
            new_present = st.checkbox(
                "נוכח",
                value=is_present,
                key=f"att_{session_id}_{s['id']}",
            )
            if new_present != is_present:
                db.upsert_attendance(conn, session_id, s["id"], new_present)
                st.rerun()

    # Summary
    att_records_fresh = {a["student_id"]: a for a in db.get_attendance(conn, session_id)}
    present_count = sum(1 for a in att_records_fresh.values() if a["present"])
    st.divider()
    st.metric("נוכחים", f"{present_count} / {len(students)}")


# ─── Lane Assignments ─────────────────────────────────────────────────────────

def _render_lanes(conn):
    st.markdown("### 🏊 שיבוץ נתיבים")

    groups = db.get_groups(conn)
    if not groups:
        st.info("אין קבוצות")
        return

    group_map = {g["name"]: g for g in groups}
    sel = st.selectbox("קבוצה", list(group_map.keys()), key="lane_grp")
    group = group_map[sel]

    sessions = db.get_sessions(conn, group["id"])
    if not sessions:
        st.info("אין שיעורים לקבוצה זו")
        return

    session_opts = {f"{s['session_date']}": s for s in sessions[:20]}
    sel_sess = st.selectbox("שיעור", list(session_opts.keys()), key="lane_sess")
    session = session_opts[sel_sess]
    session_id = session["id"]

    students = db.get_students(conn, group["id"])
    if not students:
        st.info("אין תלמידים")
        return

    num_lanes = st.number_input("מספר נתיבים", min_value=1, max_value=20, value=6, step=1)

    view_mode = st.radio("תצוגה", ["🗺️ מפה גרפית", "📋 תפריט רשימה"], horizontal=True)

    existing_assignments = {la["student_id"]: la["lane_number"] for la in db.get_lane_assignments(conn, session_id)}

    if view_mode == "📋 תפריט רשימה":
        _render_lane_list(conn, session_id, students, num_lanes, existing_assignments)
    else:
        _render_lane_map(conn, session_id, students, num_lanes, existing_assignments)


def _render_lane_list(conn, session_id, students, num_lanes, existing):
    st.markdown("#### שיבוץ לפי רשימה")
    with st.form("lane_form"):
        assignments = {}
        for s in students:
            current_lane = existing.get(s["id"], 1)
            lane = st.selectbox(
                f"{s['name']} ({s['level_color']})",
                list(range(1, num_lanes + 1)),
                index=current_lane - 1,
                key=f"lane_{s['id']}",
            )
            assignments[s["id"]] = lane

        if st.form_submit_button("💾 שמור שיבוץ", use_container_width=True):
            for student_id, lane_num in assignments.items():
                db.upsert_lane(conn, session_id, student_id, lane_num)
            st.success("✅ השיבוץ נשמר!")
            st.rerun()


def _render_lane_map(conn, session_id, students, num_lanes, existing):
    """Visual lane map with drag-and-drop via selectbox per lane."""
    st.markdown("#### מפה גרפית")

    # Show lanes as columns
    lane_cols = st.columns(min(num_lanes, 6))
    student_map = {s["id"]: s for s in students}
    new_assignments = {s["id"]: existing.get(s["id"], 1) for s in students}

    # Group students by lane
    lanes_students = {i: [] for i in range(1, num_lanes + 1)}
    for s in students:
        lane = existing.get(s["id"], 1)
        lanes_students[lane].append(s)

    for i, lane_num in enumerate(range(1, num_lanes + 1)):
        col_idx = i % len(lane_cols)
        with lane_cols[col_idx]:
            st.markdown(
                f"""<div style='background:#1a73e822;border:2px solid #1a73e8;
                    border-radius:8px;padding:8px;margin-bottom:8px;text-align:center'>
                    <b>נתיב {lane_num}</b>
                </div>""",
                unsafe_allow_html=True,
            )
            for s in lanes_students[lane_num]:
                from config import LEVEL_COLORS
                color = LEVEL_COLORS.get(s["level_color"], "#999")
                st.markdown(
                    f"""<div style='background:{color}33;border:1px solid {color};
                        border-radius:6px;padding:4px 8px;margin:2px 0;font-size:0.8rem'>
                        {s['name']}
                    </div>""",
                    unsafe_allow_html=True,
                )

    st.divider()
    st.caption("לשינוי שיבוץ, עברו ל'תפריט רשימה'")


# ─── Credits ──────────────────────────────────────────────────────────────────

def _render_credits(conn):
    st.markdown("### 💳 ניהול קרדיטים")

    role = st.session_state.user_role
    if role not in ("super_admin", "manager"):
        st.info("רק מנהלים יכולים לנהל קרדיטים")
        return

    students = db.get_students(conn)
    if not students:
        st.info("אין תלמידים")
        return

    student_map = {s["name"]: s for s in students}
    sel_name = st.selectbox("בחר תלמיד", list(student_map.keys()))
    student = student_map[sel_name]

    col1, col2 = st.columns(2)
    with col1:
        st.metric("קרדיטים נוכחיים", student["credits"])
    with col2:
        amount = st.number_input("כמות לטעינה", min_value=1.0, max_value=100.0, value=10.0, step=1.0)

    if st.button("➕ טעינת קרדיטים", type="primary"):
        db.add_credits(conn, student["id"], amount)
        st.success(f"✅ נוספו {amount:.0f} קרדיטים לתלמיד {sel_name}")
        st.rerun()

    st.divider()
    st.markdown("#### היסטוריית נוכחות")
    history = db.get_student_attendance_history(conn, student["id"])
    if history:
        rows = [
            {
                "תאריך": h["session_date"],
                "קבוצה": h["group_name"],
                "נוכח": "✅" if h["present"] else "❌",
                "קרדיט נוכה": "✅" if h["credit_deducted"] else "—",
            }
            for h in history
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("אין היסטוריית נוכחות לתלמיד זה")

    st.divider()
    st.markdown("#### ⚠️ תלמידים עם קרדיטים נמוכים")
    low_credit = [s for s in students if s["credits"] <= 2]
    if low_credit:
        rows = [{"שם": s["name"], "קרדיטים": s["credits"]} for s in low_credit]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.success("כל התלמידים בעלי קרדיטים מספיקים")
