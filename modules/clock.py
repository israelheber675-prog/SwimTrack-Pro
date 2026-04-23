"""SwimTrack Pro – Instructor Clock In/Out"""

import streamlit as st
import pandas as pd
from datetime import datetime
import db


def render(conn):
    st.markdown("## ⏱️ שעון נוכחות מדריכים")

    role = st.session_state.user_role
    user_id = st.session_state.user_id

    tab_my, tab_all = st.tabs(["⏱️ שעון שלי", "📊 כל המדריכים"])

    with tab_my:
        _render_my_clock(conn, user_id)
    with tab_all:
        if role in ("super_admin", "manager"):
            _render_all_clocks(conn)
        else:
            st.info("צפייה בשעונים של כל המדריכים זמינה למנהלים בלבד")


def _render_my_clock(conn, user_id):
    clocked_in = db.is_clocked_in(conn, user_id)
    now = datetime.now()

    if clocked_in:
        # Show current session
        record = conn.execute(
            "SELECT * FROM clock_records WHERE user_id=? AND clock_out IS NULL", (user_id,)
        ).fetchone()
        start_time = datetime.fromisoformat(record["clock_in"])
        elapsed = now - start_time
        hours = int(elapsed.total_seconds() // 3600)
        minutes = int((elapsed.total_seconds() % 3600) // 60)

        st.success(f"✅ אתה **מחובר** מ-{start_time.strftime('%H:%M')}")
        st.metric("זמן שחלף", f"{hours}:{minutes:02d} שעות")

        if st.button("🔴 יציאה", use_container_width=True, type="primary"):
            db.clock_out(conn, user_id)
            st.success("⏹️ יצאת בהצלחה!")
            st.rerun()
    else:
        st.info(f"🕐 שעה נוכחית: {now.strftime('%H:%M:%S')}")
        st.warning("אתה **לא מחובר** כרגע")
        if st.button("🟢 כניסה", use_container_width=True, type="primary"):
            db.clock_in(conn, user_id)
            st.success("✅ נכנסת בהצלחה!")
            st.rerun()

    # Personal history
    st.divider()
    st.markdown("#### ההיסטוריה שלי")
    records = db.get_clock_records(conn, user_id)
    if records:
        rows = []
        total_hours = 0.0
        for r in records:
            ci = datetime.fromisoformat(r["clock_in"])
            if r["clock_out"]:
                co = datetime.fromisoformat(r["clock_out"])
                duration_h = round((co - ci).total_seconds() / 3600, 2)
                total_hours += duration_h
                duration_str = f"{duration_h:.2f}h"
                co_str = co.strftime("%H:%M")
            else:
                duration_str = "בעבודה…"
                co_str = "—"
            rows.append({
                "תאריך": ci.strftime("%d/%m/%Y"),
                "כניסה": ci.strftime("%H:%M"),
                "יציאה": co_str,
                "שעות": duration_str,
            })

        st.dataframe(pd.DataFrame(rows[:30]), use_container_width=True, hide_index=True)
        st.metric("סה\"כ שעות (30 רשומות אחרונות)", f"{total_hours:.2f}h")
    else:
        st.info("אין רשומות נוכחות עדיין")


def _render_all_clocks(conn):
    st.markdown("#### 📊 נוכחות כל המדריכים")

    # Currently active
    active = conn.execute(
        """SELECT cr.*, u.name as user_name
           FROM clock_records cr JOIN users u ON cr.user_id=u.id
           WHERE cr.clock_out IS NULL
           ORDER BY cr.clock_in"""
    ).fetchall()

    if active:
        st.success(f"**{len(active)} מדריכים כרגע בעבודה:**")
        for a in active:
            ci = datetime.fromisoformat(a["clock_in"])
            elapsed = datetime.now() - ci
            hours = int(elapsed.total_seconds() // 3600)
            mins = int((elapsed.total_seconds() % 3600) // 60)
            st.write(f"🟢 **{a['user_name']}** — מ-{ci.strftime('%H:%M')}  ({hours}:{mins:02d} ש')")
    else:
        st.info("אין מדריכים פעילים כרגע")

    st.divider()

    # All records
    st.markdown("#### היסטוריה מלאה")
    all_records = db.get_clock_records(conn)
    if all_records:
        rows = []
        for r in all_records[:100]:
            ci = datetime.fromisoformat(r["clock_in"])
            if r["clock_out"]:
                co = datetime.fromisoformat(r["clock_out"])
                duration_h = round((co - ci).total_seconds() / 3600, 2)
                co_str = co.strftime("%d/%m %H:%M")
                dur_str = f"{duration_h:.2f}h"
            else:
                co_str = "בעבודה"
                dur_str = "—"
            rows.append({
                "מדריך": r["user_name"],
                "תאריך": ci.strftime("%d/%m/%Y"),
                "כניסה": ci.strftime("%H:%M"),
                "יציאה": co_str,
                "שעות": dur_str,
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # Summary per instructor
        st.markdown("#### סיכום לפי מדריך")
        summary = {}
        for r in all_records:
            if r["clock_out"]:
                ci = datetime.fromisoformat(r["clock_in"])
                co = datetime.fromisoformat(r["clock_out"])
                h = (co - ci).total_seconds() / 3600
                name = r["user_name"]
                summary[name] = summary.get(name, 0) + h

        if summary:
            df = pd.DataFrame(
                [{"מדריך": k, "סה\"כ שעות": round(v, 2)} for k, v in sorted(summary.items())]
            )
            st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("אין רשומות")
