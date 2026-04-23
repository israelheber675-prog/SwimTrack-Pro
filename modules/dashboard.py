"""SwimTrack Pro – Dashboard"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import date, timedelta
import db


def render(conn):
    st.markdown("## 🏠 לוח בקרה")

    stats = db.get_dashboard_stats(conn)
    role = st.session_state.user_role

    # ─── KPI Cards ────────────────────────────────────────────────────────────
    cols = st.columns(4)
    kpis = [
        ("👥", "תלמידים", stats["total_students"], None),
        ("🏊", "קבוצות פעילות", stats["active_groups"], None),
        ("📅", "שיעורים היום", stats["sessions_today"], None),
        ("⚠️", "קרדיטים נמוכים", stats["low_credit_students"], "warning" if stats["low_credit_students"] > 0 else None),
    ]
    for col, (icon, label, value, status) in zip(cols, kpis):
        with col:
            color = "#FF6B6B" if status == "warning" else "#4ECDC4"
            st.markdown(
                f"""<div style='background:{color}22;border:1px solid {color};border-radius:10px;
                    padding:16px;text-align:center;'>
                    <div style='font-size:2rem'>{icon}</div>
                    <div style='font-size:1.6rem;font-weight:bold;color:{color}'>{value}</div>
                    <div style='font-size:0.85rem;color:#666'>{label}</div>
                </div>""",
                unsafe_allow_html=True,
            )

    st.markdown("")

    # ─── Alerts row ───────────────────────────────────────────────────────────
    alert_cols = st.columns(2)

    with alert_cols[0]:
        if stats["pending_signatures"] > 0:
            st.warning(f"✍️ **{stats['pending_signatures']}** תלמידים ללא חתימת הורה בתוקף")

    with alert_cols[1]:
        if role == "super_admin" and stats["unread_alerts"] > 0:
            st.error(f"🚨 **{stats['unread_alerts']}** התראות מערכת לא נקראו")
            if st.button("צפה בהתראות"):
                st.session_state.page = "alerts"
                st.rerun()

    st.divider()

    # ─── Charts ───────────────────────────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📊 נוכחות 7 ימים אחרונים")
        _render_attendance_chart(conn)

    with col2:
        st.markdown("#### 🎨 התפלגות רמות תלמידים")
        _render_level_distribution(conn)

    st.divider()

    # ─── Recent sessions ──────────────────────────────────────────────────────
    st.markdown("#### 📅 שיעורים אחרונים")
    sessions = db.get_sessions(conn)[:10]
    if sessions:
        rows = []
        for s in sessions:
            group = db.get_group(conn, s["group_id"])
            instructor = db.get_user(conn, s["instructor_id"]) if s["instructor_id"] else None
            att = db.get_attendance(conn, s["id"])
            present = sum(1 for a in att if a["present"])
            rows.append({
                "תאריך": s["session_date"],
                "קבוצה": group["name"] if group else "-",
                "מדריך": instructor["name"] if instructor else "-",
                "נוכחים": f"{present}/{len(att)}",
                "הערות": s["notes"] or "",
            })
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("אין שיעורים עדיין")

    # ─── Super Admin extras ───────────────────────────────────────────────────
    if role == "super_admin":
        st.divider()
        st.markdown("#### 👤 ניהול משתמשים מהיר")
        users = db.get_all_users(conn)
        user_data = [
            {
                "שם": u["name"],
                "אימייל": u["email"] or "-",
                "טלפון": u["phone"] or "-",
                "תפקיד": {"super_admin": "סופר-מנהל", "manager": "מנהל", "instructor": "מדריך"}.get(u["role"], u["role"]),
                "נרשם": u["created_at"][:10],
            }
            for u in users
        ]
        st.dataframe(pd.DataFrame(user_data), use_container_width=True, hide_index=True)


def _render_attendance_chart(conn):
    today = date.today()
    dates = [today - timedelta(days=i) for i in range(6, -1, -1)]
    labels = [d.strftime("%d/%m") for d in dates]
    values = []
    for d in dates:
        sessions = conn.execute(
            "SELECT id FROM sessions WHERE session_date=?", (d.isoformat(),)
        ).fetchall()
        total_present = 0
        for s in sessions:
            att = db.get_attendance(conn, s["id"])
            total_present += sum(1 for a in att if a["present"])
        values.append(total_present)

    fig = go.Figure(go.Bar(
        x=labels, y=values,
        marker_color="#4ECDC4",
        text=values, textposition="outside",
    ))
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        height=220,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(gridcolor="#eee"),
        xaxis=dict(gridcolor="rgba(0,0,0,0)"),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_level_distribution(conn):
    rows = conn.execute(
        "SELECT level_color, COUNT(*) as cnt FROM students GROUP BY level_color"
    ).fetchall()
    if not rows:
        st.info("אין נתונים")
        return

    from config import LEVEL_COLORS
    labels = [r["level_color"] for r in rows]
    values = [r["cnt"] for r in rows]
    colors = [LEVEL_COLORS.get(l, "#999") for l in labels]

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker_colors=colors,
        hole=0.4,
    ))
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        height=220,
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=True,
        legend=dict(font=dict(size=10)),
    )
    st.plotly_chart(fig, use_container_width=True)
