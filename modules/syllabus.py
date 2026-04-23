"""SwimTrack Pro – Syllabus & Progress Tracking"""

import streamlit as st
import pandas as pd
from config import LEVEL_COLORS, SWIMMING_SYLLABUS
import db


def render(conn):
    st.markdown("## 📚 סילבוס והתקדמות")

    tab_progress, tab_syllabus, tab_upload = st.tabs(
        ["📈 מעקב התקדמות", "📖 הצג סילבוס", "⬆️ העלאת סילבוס חדש"]
    )
    with tab_progress:
        _render_progress(conn)
    with tab_syllabus:
        _render_syllabus_view(conn)
    with tab_upload:
        _render_upload_syllabus(conn)


def _render_progress(conn):
    st.markdown("### 📈 עדכון רמות תלמידים")

    groups = db.get_groups(conn)
    if not groups:
        st.info("אין קבוצות")
        return

    group_map = {g["name"]: g for g in groups}
    sel_grp = st.selectbox("קבוצה", list(group_map.keys()), key="prog_grp")
    group = group_map[sel_grp]

    students = db.get_students(conn, group["id"])
    if not students:
        st.info("אין תלמידים בקבוצה זו")
        return

    student_names = {s["name"]: s for s in students}
    sel_student = st.selectbox("תלמיד", list(student_names.keys()), key="prog_std")
    student = student_names[sel_student]

    # Level color (global)
    level_keys = list(LEVEL_COLORS.keys())
    cur_idx = level_keys.index(student["level_color"]) if student["level_color"] in level_keys else 0
    new_level = st.selectbox("🎨 צבע רמה כולל", level_keys, index=cur_idx, key="prog_level")
    if new_level != student["level_color"]:
        if st.button("עדכן רמה כולל"):
            db.update_student(conn, student["id"], level_color=new_level)
            st.success(f"✅ רמת {sel_student} עודכנה ל-{new_level}")
            st.rerun()

    st.divider()
    st.markdown("#### ✅ משימות סילבוס")

    subject = group["subject"]
    syllabus_items = db.get_syllabus(conn, subject)
    if not syllabus_items:
        st.info(f"אין סילבוס לנושא '{subject}'")
        return

    progress_records = {p["subtask_id"]: p for p in db.get_student_progress(conn, student["id"])}

    # Group by phase
    phases = {}
    for item in syllabus_items:
        phases.setdefault(item["phase_name"], []).append(item)

    color_options = list(LEVEL_COLORS.keys())

    for phase_name, items in phases.items():
        completed = sum(1 for it in items if progress_records.get(it["id"], {}).get("color", "לא התחיל") != "לא התחיל")
        pct = int(completed / len(items) * 100)

        with st.expander(f"{phase_name}  |  {completed}/{len(items)}  ({pct}%)", expanded=pct < 100):
            for item in items:
                prog = progress_records.get(item["id"])
                current_color = prog["color"] if prog else "לא התחיל"
                hex_color = LEVEL_COLORS.get(current_color, "#999")

                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(
                        f"<span style='color:{hex_color};font-weight:bold'>● </span> {item['subtask']}",
                        unsafe_allow_html=True,
                    )
                with col2:
                    idx = color_options.index(current_color) if current_color in color_options else 0
                    new_color = st.selectbox(
                        "",
                        color_options,
                        index=idx,
                        key=f"prog_{student['id']}_{item['id']}",
                        label_visibility="collapsed",
                    )
                    if new_color != current_color:
                        db.upsert_progress(conn, student["id"], item["id"], new_color, st.session_state.user_id)
                        st.rerun()


def _render_syllabus_view(conn):
    st.markdown("### 📖 סילבוסים במערכת")
    subjects = db.get_subjects(conn)
    if not subjects:
        st.info("אין סילבוסים")
        return

    sel_sub = st.selectbox("נושא", subjects)
    items = db.get_syllabus(conn, sel_sub)

    phases = {}
    for it in items:
        phases.setdefault(it["phase_name"], []).append(it)

    for phase, tasks in phases.items():
        st.markdown(f"**{phase}**")
        for i, t in enumerate(tasks, 1):
            st.write(f"  {i}. {t['subtask']}")
        st.markdown("")


def _render_upload_syllabus(conn):
    st.markdown("### ⬆️ העלאת סילבוס חדש")
    st.info(
        "📋 **תבנית קובץ CSV:**\n"
        "```\nphase_name,subtask\n"
        "שלב 1 – מבוא,משימה ראשונה\n"
        "שלב 1 – מבוא,משימה שנייה\n"
        "שלב 2 – ביניים,משימה ראשונה\n```\n\n"
        "ה-AI יזהה אוטומטית את השלבים והמשימות."
    )

    subject_name = st.text_input("שם הנושא החדש", placeholder="לדוגמה: רכיבה על סוסים")

    upload_method = st.radio("שיטת הכנסה", ["📤 העלאת CSV", "✍️ הכנסה ידנית"])

    if upload_method == "📤 העלאת CSV":
        uploaded = st.file_uploader("בחר קובץ CSV", type=["csv", "txt"])
        if uploaded and subject_name:
            content = uploaded.read().decode("utf-8", errors="ignore")
            lines = content.strip().split("\n")
            parsed = []
            order = 0
            for line in lines:
                parts = line.split(",", 1)
                if len(parts) == 2:
                    phase, task = parts[0].strip(), parts[1].strip()
                    if phase and task and phase.lower() != "phase_name":
                        parsed.append((phase, task, order))
                        order += 1

            if parsed:
                st.success(f"זוהו {len(parsed)} משימות")
                df = pd.DataFrame(parsed, columns=["שלב", "משימה", "סדר"])
                st.dataframe(df.drop(columns=["סדר"]), use_container_width=True, hide_index=True)

                if st.button("✅ ייבא סילבוס", type="primary"):
                    existing = db.get_syllabus(conn, subject_name)
                    if existing:
                        st.warning("סילבוס לנושא זה כבר קיים. אנא השתמש בשם ייחודי.")
                    else:
                        for phase, task, order_num in parsed:
                            db.add_custom_syllabus(conn, subject_name, phase, task, order_num)
                        st.success(f"✅ סילבוס '{subject_name}' נוסף בהצלחה!")
                        st.rerun()
            else:
                st.error("לא ניתן לנתח את הקובץ. בדוק את הפורמט.")

    else:  # Manual
        st.markdown("#### הכנסה ידנית")
        phase = st.text_input("שם השלב", placeholder="שלב 1 – מבוא")
        task = st.text_input("שם המשימה", placeholder="תיאור המשימה")
        if st.button("➕ הוסף משימה") and subject_name and phase and task:
            existing = db.get_syllabus(conn, subject_name)
            order = len(existing)
            db.add_custom_syllabus(conn, subject_name, phase, task, order)
            st.success(f"✅ משימה נוספה: {task}")
            st.rerun()

        # Preview current custom syllabus
        if subject_name:
            current = db.get_syllabus(conn, subject_name)
            if current:
                st.markdown(f"**סילבוס '{subject_name}' עד כה:**")
                for it in current:
                    st.write(f"• {it['phase_name']} → {it['subtask']}")
