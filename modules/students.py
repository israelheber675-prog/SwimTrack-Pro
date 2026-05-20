"""SwimTrack Pro – Student Management"""

import streamlit as st
import pandas as pd
from config import LEVEL_COLORS
import db


def render(conn):
    st.markdown("## 🎓 ניהול תלמידים")
    role = st.session_state.user_role

    tab_list, tab_add, tab_search = st.tabs(["📋 רשימת תלמידים", "➕ הוסף תלמיד", "🔍 חיפוש גלובלי"])

    with tab_list:
        _render_student_list(conn, role)

    with tab_add:
        _render_add_student(conn)

    with tab_search:
        _render_global_search(conn)


def _render_student_list(conn, role):
    groups = db.get_groups(conn)
    if not groups:
        st.info("אין קבוצות. צרו קבוצה קודם.")
        return

    group_map = {g["name"]: g["id"] for g in groups}
    all_option = "כל הקבוצות"
    sel = st.selectbox("סנן לפי קבוצה", [all_option] + list(group_map.keys()))

    group_id = group_map.get(sel) if sel != all_option else None
    students = db.get_students(conn, group_id)

    if not students:
        st.info("אין תלמידים בקבוצה זו")
        return

    # Build display table
    rows = []
    for s in students:
        group = db.get_group(conn, s["group_id"]) if s["group_id"] else None
        from db import signature_valid
        sig_ok = signature_valid(conn, s["id"])
        rows.append({
            "id": s["id"],
            "שם": s["name"],
            "קבוצה": group["name"] if group else "—",
            "רמה": s["level_color"],
            "קרדיטים": s["credits"],
            "טלפון": s["phone"] or "—",
            "הורה": s["parent_name"] or "—",
            "חתימה בתוקף": "✅" if sig_ok else "❌",
        })

    df = pd.DataFrame(rows)
    display_df = df.drop(columns=["id"])

    # Color-code level column
    def color_level(val):
        hex_color = LEVEL_COLORS.get(val, "#999999")
        return f"background-color: {hex_color}22; color: {hex_color}; font-weight:bold"

    styled = display_df.style.applymap(color_level, subset=["רמה"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # Student detail & edit
    st.divider()
    st.markdown("#### עריכת תלמיד")
    student_names = {s["name"]: s["id"] for s in students}
    selected_name = st.selectbox("בחר תלמיד לעריכה", list(student_names.keys()), key="edit_sel")
    selected_id = student_names[selected_name]
    _render_student_detail(conn, selected_id, role)


def _render_student_detail(conn, student_id, role):
    s = db.get_student(conn, student_id)
    if not s:
        return

    with st.expander(f"✏️ פרטי {s['name']}", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            new_name = st.text_input("שם", s["name"], key=f"name_{s['id']}")
            new_phone = st.text_input("טלפון", s["phone"] or "", key=f"phone_{s['id']}")
            new_email = st.text_input("אימייל", s["email"] or "", key=f"email_{s['id']}")
            new_birth = st.text_input("תאריך לידה", s["birth_date"] or "", key=f"birth_{s['id']}")

        with col2:
            new_parent = st.text_input("שם הורה", s["parent_name"] or "", key=f"parent_{s['id']}")
            new_parent_ph = st.text_input("טלפון הורה", s["parent_phone"] or "", key=f"parentph_{s['id']}")
            new_credits = st.number_input("קרדיטים", value=float(s["credits"]), step=1.0, key=f"cred_{s['id']}")
            new_notes = st.text_area("הערות", s["notes"] or "", key=f"notes_{s['id']}", height=80)

        # Level color picker
        level_keys = list(LEVEL_COLORS.keys())
        cur_idx = level_keys.index(s["level_color"]) if s["level_color"] in level_keys else 0
        new_level = st.selectbox(
            "🎨 צבע רמה",
            level_keys,
            index=cur_idx,
            key=f"level_{s['id']}",
            format_func=lambda k: f"{k}  ●",
        )

        # Group assignment
        groups = db.get_groups(conn)
        group_map = {g["name"]: g["id"] for g in groups}
        current_group = db.get_group(conn, s["group_id"]) if s["group_id"] else None
        current_group_name = current_group["name"] if current_group else "—"
        grp_opts = list(group_map.keys())
        grp_idx = grp_opts.index(current_group_name) if current_group_name in grp_opts else 0
        new_group_name = st.selectbox("קבוצה", grp_opts, index=grp_idx, key=f"grp_{s['id']}")

        col_save, col_del = st.columns(2)
        with col_save:
            if role in ("super_admin", "manager", "instructor") and st.button("💾 שמור שינויים", key=f"save_{s['id']}"):
                db.update_student(
                    conn, s["id"],
                    name=new_name,
                    phone=new_phone or None,
                    email=new_email or None,
                    birth_date=new_birth or None,
                    parent_name=new_parent or None,
                    parent_phone=new_parent_ph or None,
                    credits=new_credits,
                    notes=new_notes or None,
                    level_color=new_level,
                    group_id=group_map.get(new_group_name),
                )
                st.success("✅ הנתונים נשמרו בהצלחה!")
                st.rerun()

        with col_del:
            if role == "super_admin":
                if st.button("🗑️ מחק תלמיד", key=f"del_{s['id']}"):
                    st.session_state[f"confirm_del_{s['id']}"] = True

        if st.session_state.get(f"confirm_del_{s['id']}"):
            st.warning(f"האם אתה בטוח שברצונך למחוק את **{s['name']}**? פעולה זו אינה הפיכה.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ כן, מחק", key=f"yes_del_{s['id']}"):
                    conn.execute("DELETE FROM students WHERE id=?", (s["id"],))
                    conn.commit()
                    st.success("התלמיד נמחק")
                    del st.session_state[f"confirm_del_{s['id']}"]
                    st.rerun()
            with c2:
                if st.button("❌ ביטול", key=f"no_del_{s['id']}"):
                    del st.session_state[f"confirm_del_{s['id']}"]


def _render_add_student(conn):
    st.markdown("### ➕ הוספת תלמיד חדש")

    groups = db.get_groups(conn)
    if not groups:
        st.warning("אין קבוצות. צרו קבוצה תחילה.")
        return

    group_map = {g["name"]: g["id"] for g in groups}

    with st.form("add_student_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("שם מלא *")
            phone = st.text_input("טלפון")
            email = st.text_input("אימייל")
            birth_date = st.text_input("תאריך לידה (YYYY-MM-DD)")
        with col2:
            parent_name = st.text_input("שם הורה")
            parent_phone = st.text_input("טלפון הורה")
            credits = st.number_input("קרדיטים ראשוניים", min_value=0.0, value=10.0, step=1.0)
            notes = st.text_area("הערות", height=80)

        group_sel = st.selectbox("קבוצה *", list(group_map.keys()))
        submitted = st.form_submit_button("➕ הוסף תלמיד", use_container_width=True, type="primary")

    if submitted:
        if not name:
            st.error("שם הוא שדה חובה")
            return
        db.create_student(
            conn, name, email or None, phone or None, parent_name or None,
            parent_phone or None, birth_date or None, notes or None,
            group_map[group_sel], credits,
        )
        st.success(f"✅ התלמיד **{name}** נוסף בהצלחה!")
        st.rerun()


def _render_global_search(conn):
    st.markdown("### 🔍 חיפוש גלובלי")
    st.caption("חפש לפי שם, אימייל, טלפון, הורה, צבע רמה או הערות")

    query = st.text_input("🔎 חיפוש", placeholder="לדוגמה: אדום, ישראל, 050...")

    if query:
        results = db.search_students(conn, query)
        if results:
            st.success(f"נמצאו {len(results)} תלמידים")
            rows = []
            for s in results:
                group = db.get_group(conn, s["group_id"]) if s["group_id"] else None
                rows.append({
                    "שם": s["name"],
                    "קבוצה": group["name"] if group else "—",
                    "רמה": s["level_color"],
                    "קרדיטים": s["credits"],
                    "טלפון": s["phone"] or "—",
                    "הורה": s["parent_name"] or "—",
                })
            df = pd.DataFrame(rows)

            def hl(val):
                if query.lower() in str(val).lower():
                    return "background-color: #fff3cd"
                return ""

            st.dataframe(df.style.applymap(hl), use_container_width=True, hide_index=True)
        else:
            st.info("לא נמצאו תלמידים תואמים")
    else:
        # Show all students summary
        all_students = db.get_students(conn)
        st.info(f"סה\"כ {len(all_students)} תלמידים במערכת. הזן מונח חיפוש.")
