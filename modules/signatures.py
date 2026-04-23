"""SwimTrack Pro – Annual Parent Signatures (Health Declarations)"""

import streamlit as st
import pandas as pd
from datetime import datetime
import db

DECLARATION_TEXT = """הצהרת בריאות – הורה / אפוטרופוס

אני החתום מטה מצהיר/ה כי ילדי/ת הנ"ל:
1. כשיר/ה מבחינה בריאותית להשתתף בפעילות שחייה.
2. אינו/ה סובל/ת ממצב רפואי שעלול לסכן אותו/ה במים.
3. קיבל/ה הנחיות בטיחות בסיסיות.
4. הנני מסכים/ה לתנאי הפעילות ולמדיניות הבטיחות.

חתימה זו בתוקף לשנה אחת מיום חתימתה."""


def render(conn):
    st.markdown("## ✍️ חתימות הורים")

    role = st.session_state.user_role
    tab_sign, tab_status = st.tabs(["✍️ חתימה חדשה", "📋 סטטוס חתימות"])

    with tab_sign:
        _render_sign(conn)
    with tab_status:
        _render_status(conn, role)


def _render_sign(conn):
    st.markdown("### ✍️ הצהרת בריאות שנתית")
    st.info("נדרשת חתימת הורה פעם בשנה לכל תלמיד.")

    students = db.get_students(conn)
    if not students:
        st.info("אין תלמידים רשומים")
        return

    student_map = {f"{s['name']} (ק: {_group_name(conn, s)})": s for s in students}
    sel = st.selectbox("בחר תלמיד", list(student_map.keys()))
    student = student_map[sel]

    # Check existing signature
    valid = db.signature_valid(conn, student["id"])
    if valid:
        sig = db.get_latest_signature(conn, student["id"])
        st.success(f"✅ קיימת חתימה בתוקף מ-{sig['signed_at'][:10]}")
        override = st.checkbox("חתום שוב (יחליף חתימה קיימת)")
        if not override:
            return

    st.markdown("#### הצהרת בריאות")
    st.markdown(
        f"""<div style='background:#f8f9fa;border:1px solid #dee2e6;border-radius:8px;
            padding:16px;font-size:0.9rem;white-space:pre-line;direction:rtl'>
{DECLARATION_TEXT}
        </div>""",
        unsafe_allow_html=True,
    )

    st.markdown("#### פרטי ההורה / האפוטרופוס")
    parent_name = st.text_input(
        "שם ההורה / האפוטרופוס",
        value=student["parent_name"] or "",
        placeholder="שם מלא",
    )

    st.markdown("#### חתימה דיגיטלית")

    # Try drawable canvas; fallback to text input
    signature_data = None
    canvas_available = False
    try:
        from streamlit_drawable_canvas import st_canvas
        canvas_available = True
    except ImportError:
        pass

    if canvas_available:
        st.caption("חתום בעזרת העכבר / מסך מגע:")
        canvas_result = st_canvas(
            fill_color="rgba(255,255,255,0)",
            stroke_width=3,
            stroke_color="#1a1a2e",
            background_color="#FFFFFF",
            height=150,
            width=400,
            drawing_mode="freedraw",
            key=f"sig_canvas_{student['id']}",
        )
        if canvas_result.image_data is not None:
            import numpy as np
            # Check if anything was drawn (not all white)
            arr = canvas_result.image_data
            if arr is not None and arr.sum() > 0:
                # Convert to base64
                from PIL import Image
                import io
                import base64
                img = Image.fromarray(arr.astype("uint8"), "RGBA")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                signature_data = base64.b64encode(buf.getvalue()).decode()
    else:
        st.caption("חתימה דיגיטלית (הקלד שם לאישור):")
        typed_sig = st.text_input(
            "הקלד שמך המלא לאישור הצהרה זו",
            placeholder="חתימה: שם מלא",
            key=f"sig_text_{student['id']}",
        )
        if typed_sig.strip():
            signature_data = f"TEXT_SIG:{typed_sig.strip()}"

    if st.button("✅ אשר וחתום", type="primary", use_container_width=True):
        if not parent_name.strip():
            st.error("נא למלא שם הורה")
            return
        if not signature_data:
            st.error("נא לחתום על ההצהרה")
            return

        db.save_signature(conn, student["id"], parent_name.strip(), signature_data, DECLARATION_TEXT)
        st.success(f"✅ ההצהרה נחתמה בהצלחה עבור {student['name']}!")
        st.balloons()
        st.rerun()


def _render_status(conn, role):
    st.markdown("### 📋 סטטוס חתימות")
    students = db.get_students(conn)
    if not students:
        st.info("אין תלמידים")
        return

    rows = []
    for s in students:
        sig = db.get_latest_signature(conn, s["id"])
        valid = db.signature_valid(conn, s["id"])
        group = _group_name(conn, s)
        rows.append({
            "שם תלמיד": s["name"],
            "קבוצה": group,
            "שם הורה": sig["parent_name"] if sig else "—",
            "תאריך חתימה": sig["signed_at"][:10] if sig else "לא חתום",
            "סטטוס": "✅ בתוקף" if valid else ("⚠️ פג תוקף" if sig else "❌ חסר"),
        })

    df = pd.DataFrame(rows)

    def color_status(val):
        if "✅" in str(val):
            return "background-color: #d4edda"
        elif "⚠️" in str(val):
            return "background-color: #fff3cd"
        return "background-color: #f8d7da"

    st.dataframe(
        df.style.applymap(color_status, subset=["סטטוס"]),
        use_container_width=True,
        hide_index=True,
    )

    missing = [r for r in rows if r["סטטוס"] != "✅ בתוקף"]
    if missing:
        st.warning(f"⚠️ {len(missing)} תלמידים ללא חתימה בתוקף. יש לסדר חתימות!")


def _group_name(conn, student) -> str:
    if student["group_id"]:
        g = db.get_group(conn, student["group_id"])
        return g["name"] if g else "—"
    return "—"
