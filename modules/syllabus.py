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
    st.markdown("### ⬆️ העלאת / עדכון סילבוס")

    with st.expander("📋 תבנית קובץ CSV – לחץ לפרטים"):
        st.markdown(
            "**פורמט שורה:** `שם_שלב,שם_משימה`\n\n"
            "```\nphase_name,subtask\n"
            "שלב 1 – מבוא,משימה ראשונה\n"
            "שלב 1 – מבוא,משימה שנייה\n"
            "שלב 2 – ביניים,משימה ראשונה\n```\n\n"
            "ניתן גם להדביק טקסט חופשי – המערכת תנסה לזהות שלבים ומשימות אוטומטית."
        )

    existing_subjects = db.get_subjects(conn)
    col1, col2 = st.columns([3, 1])
    with col1:
        subject_name = st.text_input(
            "שם הנושא",
            placeholder="לדוגמה: שחייה / רכיבה על סוסים",
        )
    with col2:
        st.write("")
        st.write("")
        if subject_name and subject_name in existing_subjects:
            st.warning("קיים ✱")
        elif subject_name:
            st.success("חדש ✓")

    replace_existing = False
    if subject_name and subject_name in existing_subjects:
        replace_existing = st.checkbox(
            f"🔄 החלף את הסילבוס הקיים של **'{subject_name}'** בגרסה החדשה",
            value=False,
        )
        if replace_existing:
            st.warning(
                "⚠️ כל המשימות הקיימות ייחלפו. היסטוריית התקדמות התלמידים **לא** תימחק."
            )

    upload_method = st.radio("שיטת הכנסה", ["📤 העלאת CSV", "✍️ הכנסה ידנית"], horizontal=True)

    if upload_method == "📤 העלאת CSV":
        _upload_csv(conn, subject_name, replace_existing)
    else:
        _manual_entry(conn, subject_name, replace_existing)


def _parse_csv_content(content: str) -> list:
    """Parse CSV or free-text into list of (phase, task, order)."""
    lines = content.strip().splitlines()
    parsed = []
    order = 0
    current_phase = "שלב 1"

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Standard CSV: phase,task
        if "," in line:
            parts = line.split(",", 1)
            phase, task = parts[0].strip(), parts[1].strip()
            if phase.lower() in ("phase_name", "שם_שלב", "שלב"):
                continue  # header row
            if phase and task:
                current_phase = phase
                parsed.append((phase, task, order))
                order += 1
        else:
            # Free text: lines starting with "שלב" are phase headers; rest are tasks
            import re
            if re.match(r"^שלב\s*\d", line) or re.match(r"^phase\s*\d", line, re.I):
                current_phase = line
            elif len(line) > 3:
                parsed.append((current_phase, line, order))
                order += 1
    return parsed


def _upload_csv(conn, subject_name, replace_existing):
    uploaded = st.file_uploader(
        "בחר קובץ CSV / TXT",
        type=["csv", "txt"],
        key="syl_upload",
    )
    if not uploaded:
        return
    if not subject_name:
        st.error("נא להזין שם נושא לפני הייבוא")
        return

    content = uploaded.read().decode("utf-8-sig", errors="ignore")
    parsed = _parse_csv_content(content)

    if not parsed:
        st.error("לא ניתן לנתח את הקובץ. בדוק את הפורמט.")
        return

    st.success(f"זוהו **{len(parsed)}** משימות")
    df = pd.DataFrame(parsed, columns=["שלב", "משימה", "סדר"])
    st.dataframe(df.drop(columns=["סדר"]), use_container_width=True, hide_index=True)

    btn_label = "🔄 החלף סילבוס" if replace_existing else "✅ ייבא סילבוס"
    if st.button(btn_label, type="primary"):
        if replace_existing:
            conn.execute("DELETE FROM syllabus WHERE subject=?", (subject_name,))
            conn.commit()
        for phase, task, order_num in parsed:
            db.add_custom_syllabus(conn, subject_name, phase, task, order_num)
        action = "עודכן" if replace_existing else "נוסף"
        st.success(f"✅ סילבוס '{subject_name}' {action} בהצלחה! ({len(parsed)} משימות)")
        st.rerun()


def _manual_entry(conn, subject_name, replace_existing):
    st.markdown("#### ✍️ הכנסה ידנית")

    if replace_existing:
        if st.button("🗑️ מחק סילבוס קיים ופתח מחדש", type="secondary"):
            conn.execute("DELETE FROM syllabus WHERE subject=?", (subject_name,))
            conn.commit()
            st.success("הסילבוס הקיים נמחק. הוסף משימות חדשות.")
            st.rerun()

    phase = st.text_input("שם השלב", placeholder="שלב 1 – מבוא", key="man_phase")
    task  = st.text_input("שם המשימה", placeholder="תיאור המשימה", key="man_task")
    if st.button("➕ הוסף משימה") and subject_name and phase and task:
        existing = db.get_syllabus(conn, subject_name)
        db.add_custom_syllabus(conn, subject_name, phase, task, len(existing))
        st.success(f"✅ משימה נוספה: {task}")
        st.rerun()

    if subject_name:
        current = db.get_syllabus(conn, subject_name)
        if current:
            st.markdown(f"**סילבוס '{subject_name}' עד כה – {len(current)} משימות:**")
            phases_d = {}
            for it in current:
                phases_d.setdefault(it["phase_name"], []).append(it["subtask"])
            for ph, tasks in phases_d.items():
                st.markdown(f"*{ph}*")
                for t in tasks:
                    st.write(f"  • {t}")
