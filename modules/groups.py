"""SwimTrack Pro – Group Management"""

import streamlit as st
import pandas as pd
import db


def render(conn):
    st.markdown("## 👥 ניהול קבוצות")
    role = st.session_state.user_role

    tab_list, tab_new, tab_archived = st.tabs(["📋 קבוצות פעילות", "➕ קבוצה חדשה", "🗃️ ארכיון"])

    with tab_list:
        _render_active_groups(conn, role)

    with tab_new:
        _render_new_group(conn)

    with tab_archived:
        _render_archived_groups(conn, role)


def _render_active_groups(conn, role):
    groups = db.get_groups(conn, include_archived=False)
    if not groups:
        st.info("אין קבוצות פעילות. פתחו קבוצה חדשה!")
        return

    user_id = st.session_state.user_id

    for g in groups:
        # Instructors see only their own groups
        is_my_group = (g["instructor_id"] == user_id or
                       g["manager_id"] == user_id or
                       role in ("super_admin", "manager"))
        if not is_my_group:
            continue

        with st.expander(f"🏊 {g['name']}  |  {g['subject']}", expanded=False):
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                manager = db.get_user(conn, g["manager_id"]) if g["manager_id"] else None
                st.write(f"**מנהל:** {manager['name'] if manager else '—'}")
                instructor = db.get_user(conn, g["instructor_id"]) if g["instructor_id"] else None
                st.write(f"**מדריך:** {instructor['name'] if instructor else '—'}")
                st.write(f"**נוצר:** {g['created_at'][:10]}")

            with col2:
                students = db.get_students(conn, g["id"])
                st.write(f"**תלמידים:** {len(students)}")
                if students:
                    names = ", ".join(s["name"] for s in students[:5])
                    if len(students) > 5:
                        names += f" +{len(students)-5}"
                    st.caption(names)

            with col3:
                if role in ("super_admin", "manager") or g["instructor_id"] == user_id:
                    if st.button("🔒 ארכב", key=f"arch_{g['id']}"):
                        st.session_state[f"confirm_arch_{g['id']}"] = True

                    if st.session_state.get(f"confirm_arch_{g['id']}"):
                        st.warning("האם אתה בטוח? הקבוצה תועבר לארכיון.")
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("✅ כן", key=f"yes_{g['id']}"):
                                db.archive_group(conn, g["id"])
                                del st.session_state[f"confirm_arch_{g['id']}"]
                                st.success("הקבוצה הועברה לארכיון")
                                st.rerun()
                        with c2:
                            if st.button("❌ ביטול", key=f"no_{g['id']}"):
                                del st.session_state[f"confirm_arch_{g['id']}"]
                                st.rerun()

            # Assign instructor – managers and admins only
            if role in ("super_admin", "manager"):
                st.divider()
                instructors = db.get_users_by_role(conn, "instructor")
                managers = db.get_users_by_role(conn, "manager")
                all_instructors = list(instructors) + list(managers)
                opts = {u["name"]: u["id"] for u in all_instructors}
                opts_keys = ["—"] + list(opts.keys())
                current = instructor["name"] if instructor else "—"
                idx = opts_keys.index(current) if current in opts_keys else 0
                with st.form(f"assign_{g['id']}"):
                    sel = st.selectbox("שנה מדריך לקבוצה", opts_keys, index=idx)
                    if st.form_submit_button("שמור"):
                        db.update_group(conn, g["id"], instructor_id=opts.get(sel))
                        st.success("המדריך עודכן!")
                        st.rerun()


def _render_new_group(conn):
    st.markdown("### ➕ פתיחת קבוצה חדשה")
    st.info("⚠️ שינוי נושא מחייב פתיחת קבוצה חדשה. נתוני הקבוצה הקיימת יישמרו בארכיון.")

    role = st.session_state.user_role
    user_id = st.session_state.user_id

    subjects_in_db = list(db.get_subjects(conn))
    default_subjects = ["שחייה", "רכיבה על סוסים", "כדורגל", "כדורסל", "אמנויות לחימה", "אחר"]
    all_subjects = list(dict.fromkeys(default_subjects + subjects_in_db))

    with st.form("new_group_form"):
        name = st.text_input("שם הקבוצה *", placeholder="קבוצת ילדים א'")
        subject_sel = st.selectbox("נושא *", all_subjects)
        custom_subject = st.text_input("נושא מותאם (אם בחרת 'אחר')", placeholder="שם הנושא")

        # Manager – admins/managers choose; instructors default to themselves as manager
        if role in ("super_admin", "manager"):
            managers = db.get_users_by_role(conn, "manager")
            super_admins = db.get_users_by_role(conn, "super_admin")
            mgr_options = list(managers) + list(super_admins)
            mgr_map = {u["name"]: u["id"] for u in mgr_options}
            mgr_sel = st.selectbox("מנהל קבוצה", list(mgr_map.keys()) if mgr_map else ["—"])
            manager_id_field = mgr_map.get(mgr_sel) if mgr_map else user_id
        else:
            # Instructor: they are the manager of their own group
            me = db.get_user(conn, user_id)
            st.info(f"הקבוצה תירשם תחתך: **{me['name']}**")
            manager_id_field = None  # will use user_id below
            mgr_map = {}

        # Instructor assignment
        instructors = db.get_users_by_role(conn, "instructor")
        inst_map = {u["name"]: u["id"] for u in instructors}
        inst_opts = ["— אני המדריך —"] + list(inst_map.keys())
        inst_sel = st.selectbox("מדריך", inst_opts)

        submitted = st.form_submit_button("צור קבוצה", use_container_width=True, type="primary")

    if submitted:
        if not name:
            st.error("שם הקבוצה הוא שדה חובה")
            return
        subject = custom_subject.strip() if subject_sel == "אחר" and custom_subject else subject_sel

        if role in ("super_admin", "manager"):
            manager_id = manager_id_field or user_id
        else:
            manager_id = user_id   # instructor manages their own group

        if inst_sel == "— אני המדריך —":
            instructor_id = user_id
        else:
            instructor_id = inst_map.get(inst_sel)

        db.create_group(conn, name, subject, manager_id, instructor_id)
        st.success(f"✅ קבוצה **{name}** נוצרה בהצלחה!")
        st.rerun()


def _render_archived_groups(conn, role):
    groups = conn.execute(
        "SELECT * FROM groups WHERE archived=1 ORDER BY archived_at DESC"
    ).fetchall()
    if not groups:
        st.info("אין קבוצות בארכיון")
        return

    rows = []
    for g in groups:
        manager = db.get_user(conn, g["manager_id"]) if g["manager_id"] else None
        students = db.get_students(conn, g["id"])
        rows.append({
            "שם": g["name"],
            "נושא": g["subject"],
            "מנהל": manager["name"] if manager else "—",
            "תלמידים": len(students),
            "נוצר": g["created_at"][:10],
            "הועבר לארכיון": (g["archived_at"] or "")[:10],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption("הנתונים בארכיון נשמרים ואפשר לעיין בהם בכל עת.")
