"""SwimTrack Pro – WhatsApp Reports in 6 Languages"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, timedelta
from config import WHATSAPP_TEMPLATES
import db


def render(conn):
    st.markdown("## 📊 דוחות ו-WhatsApp")

    tab_whatsapp, tab_stats, tab_data = st.tabs(
        ["📱 דוח WhatsApp", "📈 סטטיסטיקות", "📋 נתונים גולמיים"]
    )

    with tab_whatsapp:
        _render_whatsapp(conn)
    with tab_stats:
        _render_stats(conn)
    with tab_data:
        _render_raw_data(conn)


def _render_whatsapp(conn):
    st.markdown("### 📱 יצירת דוח WhatsApp")

    col1, col2 = st.columns(2)
    with col1:
        groups = db.get_groups(conn)
        if not groups:
            st.info("אין קבוצות")
            return
        group_map = {g["name"]: g for g in groups}
        sel_grp = st.selectbox("קבוצה", list(group_map.keys()))
        group = group_map[sel_grp]

    with col2:
        rep_date = st.date_input("תאריך שיעור לדוח", value=date.today())

    # Get session for that date
    session = conn.execute(
        "SELECT * FROM sessions WHERE group_id=? AND session_date=?",
        (group["id"], rep_date.isoformat()),
    ).fetchone()

    present = 0
    total = len(db.get_students(conn, group["id"]))
    instructor_name = "—"

    if session:
        att = db.get_attendance(conn, session["id"])
        present = sum(1 for a in att if a["present"])
        instructor = db.get_user(conn, session["instructor_id"]) if session["instructor_id"] else None
        instructor_name = instructor["name"] if instructor else "—"

    notes = st.text_area("הערות לדוח", placeholder="כתוב הערות מיוחדות לשיעור זה...")

    # Product recommendation
    products = db.get_products(conn, active_only=True)
    product_name = "—"
    product_link = "—"
    if products:
        product_opts = {p["name"]: p for p in products}
        include_product = st.checkbox("כלול המלצת מוצר מהחנות")
        if include_product:
            sel_prod = st.selectbox("בחר מוצר לקידום", list(product_opts.keys()))
            product_name = sel_prod
            product_link = product_opts[sel_prod]["external_link"] or "—"

    # Language selection
    language = st.selectbox("שפת הדוח", list(WHATSAPP_TEMPLATES.keys()))

    if st.button("📋 צור דוח", type="primary", use_container_width=True):
        template = WHATSAPP_TEMPLATES[language]
        report_text = template.format(
            date=rep_date.strftime("%d/%m/%Y"),
            group=sel_grp,
            instructor=instructor_name,
            present=present,
            total=total,
            notes=notes or "—",
            product=product_name,
            product_link=product_link,
        )
        st.markdown("#### 📋 הדוח מוכן – העתק ושלח:")
        st.text_area(
            "דוח WhatsApp",
            value=report_text,
            height=300,
            key="wa_report",
        )
        st.success("✅ הדוח מוכן! העתק את הטקסט ושלח לווטסאפ.")

        # Save dry stat
        conn.execute(
            "INSERT INTO dry_statistics (stat_date,stat_key,stat_value,notes) VALUES (?,?,?,?)",
            (date.today().isoformat(), "whatsapp_report_generated", 1, f"group={sel_grp}, lang={language}"),
        )
        conn.commit()


def _render_stats(conn):
    st.markdown("### 📈 סטטיסטיקות")

    period = st.selectbox("תקופה", ["7 ימים", "30 ימים", "90 ימים", "כל הזמן"])
    period_days = {"7 ימים": 7, "30 ימים": 30, "90 ימים": 90, "כל הזמן": 99999}[period]
    since = (date.today() - timedelta(days=period_days)).isoformat()

    col1, col2, col3 = st.columns(3)
    with col1:
        sessions_count = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE session_date >= ?", (since,)
        ).fetchone()[0]
        st.metric("שיעורים", sessions_count)
    with col2:
        present_count = conn.execute(
            """SELECT COUNT(*) FROM attendance a
               JOIN sessions s ON a.session_id=s.id
               WHERE a.present=1 AND s.session_date >= ?""",
            (since,),
        ).fetchone()[0]
        st.metric("סה\"כ נוכחויות", present_count)
    with col3:
        total_students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        st.metric("תלמידים רשומים", total_students)

    st.divider()

    # Attendance per group
    st.markdown("#### נוכחות לפי קבוצה")
    groups = db.get_groups(conn, include_archived=False)
    if groups:
        grp_data = []
        for g in groups:
            sessions = conn.execute(
                "SELECT id FROM sessions WHERE group_id=? AND session_date >= ?",
                (g["id"], since),
            ).fetchall()
            total_p = 0
            for s in sessions:
                att = db.get_attendance(conn, s["id"])
                total_p += sum(1 for a in att if a["present"])
            grp_data.append({"קבוצה": g["name"], "נוכחויות": total_p})

        if grp_data:
            df = pd.DataFrame(grp_data)
            fig = px.bar(df, x="קבוצה", y="נוכחויות", color="קבוצה",
                         color_discrete_sequence=px.colors.qualitative.Pastel)
            fig.update_layout(margin=dict(l=0, r=0, t=20, b=0), height=300,
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

    # Instructor hours
    st.markdown("#### שעות עבודה מדריכים")
    clock_data = conn.execute(
        """SELECT u.name, cr.clock_in, cr.clock_out
           FROM clock_records cr JOIN users u ON cr.user_id=u.id
           WHERE cr.clock_in >= ? ORDER BY cr.clock_in DESC""",
        (since,),
    ).fetchall()
    if clock_data:
        rows = []
        for r in clock_data:
            if r["clock_out"]:
                from datetime import datetime
                ci = datetime.fromisoformat(r["clock_in"])
                co = datetime.fromisoformat(r["clock_out"])
                hours = round((co - ci).total_seconds() / 3600, 2)
            else:
                hours = None
            rows.append({"מדריך": r["name"], "כניסה": r["clock_in"][:16],
                         "יציאה": r["clock_out"][:16] if r["clock_out"] else "בעבודה",
                         "שעות": hours or "—"})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("אין נתוני שעון נוכחות לתקופה זו")


def _render_raw_data(conn):
    st.markdown("### 📋 ייצוא נתונים")
    role = st.session_state.user_role

    export_type = st.selectbox("סוג הנתונים", [
        "תלמידים", "שיעורים", "נוכחות", "קבוצות", "מלאי", "סטטיסטיקות יבשות"
    ])

    if st.button("📥 טען נתונים", use_container_width=True):
        if export_type == "תלמידים":
            rows = db.get_students(conn)
            df = pd.DataFrame([dict(r) for r in rows])
            # Remove password fields if accidentally included
            df = df.drop(columns=["password_hash", "salt"], errors="ignore")

        elif export_type == "שיעורים":
            rows = db.get_sessions(conn)
            df = pd.DataFrame([dict(r) for r in rows])

        elif export_type == "נוכחות":
            rows = conn.execute(
                """SELECT a.*, s.session_date, st.name as student_name, g.name as group_name
                   FROM attendance a
                   JOIN sessions s ON a.session_id=s.id
                   JOIN students st ON a.student_id=st.id
                   JOIN groups g ON s.group_id=g.id
                   ORDER BY s.session_date DESC"""
            ).fetchall()
            df = pd.DataFrame([dict(r) for r in rows])

        elif export_type == "קבוצות":
            rows = db.get_groups(conn, include_archived=True)
            df = pd.DataFrame([dict(r) for r in rows])

        elif export_type == "מלאי":
            rows = db.get_inventory(conn)
            df = pd.DataFrame([dict(r) for r in rows])

        else:  # סטטיסטיקות יבשות
            rows = conn.execute("SELECT * FROM dry_statistics ORDER BY stat_date DESC").fetchall()
            df = pd.DataFrame([dict(r) for r in rows])

        if df.empty:
            st.info("אין נתונים לייצוא")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
            csv = df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label=f"⬇️ הורד CSV – {export_type}",
                data=csv.encode("utf-8-sig"),
                file_name=f"swimtrack_{export_type}_{date.today()}.csv",
                mime="text/csv",
            )
