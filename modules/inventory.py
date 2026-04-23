"""SwimTrack Pro – Inventory Management"""

import streamlit as st
import pandas as pd
from datetime import datetime
import db


DEFAULT_CATEGORIES = [
    "ציוד שחייה", "ציוד בטיחות", "ציוד חינוכי", "ביגוד וציוד אישי",
    "ניקוי ותחזוקה", "משרד", "אחר"
]


def render(conn):
    st.markdown("## 📦 ניהול מלאי")
    role = st.session_state.user_role

    tab_view, tab_edit = st.tabs(["📋 צפייה במלאי", "✏️ עריכה"])

    with tab_view:
        _render_inventory_view(conn)
    with tab_edit:
        if role in ("super_admin", "manager"):
            _render_inventory_edit(conn)
        else:
            st.info("רק מנהלים יכולים לערוך את המלאי")


def _render_inventory_view(conn):
    items = db.get_inventory(conn)
    if not items:
        st.info("המלאי ריק. הוסף פריטים בלשונית 'עריכה'.")
        return

    categories = db.get_inventory_categories(conn)

    # Category filter
    sel_cat = st.selectbox("סנן לפי קטגוריה", ["הכל"] + categories)
    filtered = db.get_inventory(conn, sel_cat if sel_cat != "הכל" else None)

    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("סה\"כ פריטים", len(filtered))
    with col2:
        low_stock = [i for i in filtered if i["quantity"] <= 2]
        st.metric("מלאי נמוך (≤2)", len(low_stock))
    with col3:
        total_qty = sum(i["quantity"] for i in filtered)
        st.metric("סה\"כ יחידות", total_qty)

    if low_stock:
        st.warning(f"⚠️ {len(low_stock)} פריטים במלאי נמוך: " + ", ".join(i["name"] for i in low_stock))

    # Table
    rows = [
        {
            "שם": i["name"],
            "קטגוריה": i["category"],
            "כמות": i["quantity"],
            "הערות": i["notes"] or "—",
            "עודכן": i["updated_at"][:10],
            "מצב": "⚠️ נמוך" if i["quantity"] <= 2 else ("❌ אזל" if i["quantity"] == 0 else "✅ תקין"),
        }
        for i in filtered
    ]
    df = pd.DataFrame(rows)

    def color_qty(val):
        if val == 0:
            return "background-color: #ffcccc"
        elif val <= 2:
            return "background-color: #fff3cd"
        return ""

    st.dataframe(
        df.style.applymap(color_qty, subset=["כמות"]),
        use_container_width=True,
        hide_index=True,
    )


def _render_inventory_edit(conn):
    st.markdown("### ✏️ הוספה / עריכת פריט")

    existing_cats = db.get_inventory_categories(conn)
    all_cats = list(dict.fromkeys(DEFAULT_CATEGORIES + existing_cats))

    with st.form("add_item_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("שם הפריט *", placeholder="משקפי שחייה")
            cat_sel = st.selectbox("קטגוריה", all_cats + ["➕ קטגוריה חדשה"])
        with col2:
            custom_cat = st.text_input("קטגוריה חדשה (אם בחרת '➕')", placeholder="שם הקטגוריה")
            quantity = st.number_input("כמות", min_value=0, value=1, step=1)

        notes = st.text_input("הערות", placeholder="מיקום, ספק וכו'")
        submitted = st.form_submit_button("💾 שמור פריט", use_container_width=True, type="primary")

    if submitted:
        if not name:
            st.error("שם הפריט הוא שדה חובה")
            return
        category = custom_cat.strip() if cat_sel == "➕ קטגוריה חדשה" and custom_cat else cat_sel
        db.upsert_inventory(conn, name, category, quantity, notes or "")
        st.success(f"✅ הפריט '{name}' נשמר!")
        st.rerun()

    # Quick quantity update
    st.divider()
    st.markdown("### 🔢 עדכון כמות מהיר")
    items = db.get_inventory(conn)
    if items:
        item_map = {f"{i['name']} ({i['category']})": i for i in items}
        sel_item_name = st.selectbox("בחר פריט", list(item_map.keys()))
        sel_item = item_map[sel_item_name]

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("כמות נוכחית", sel_item["quantity"])
        with col2:
            delta = st.number_input("שינוי", value=0, step=1)
        with col3:
            st.write("")
            st.write("")
            if st.button("עדכן"):
                new_qty = max(0, sel_item["quantity"] + delta)
                db.upsert_inventory(conn, sel_item["name"], sel_item["category"],
                                    new_qty, sel_item["notes"] or "")
                st.success(f"כמות עודכנה ל-{new_qty}")
                st.rerun()

    # Delete item
    st.divider()
    st.markdown("### 🗑️ מחיקת פריט")
    if items:
        del_map = {f"{i['name']} ({i['category']})": i for i in items}
        sel_del = st.selectbox("בחר פריט למחיקה", list(del_map.keys()), key="del_item")
        if st.button("🗑️ מחק פריט", type="secondary"):
            db.delete_inventory_item(conn, del_map[sel_del]["id"])
            st.success("הפריט נמחק")
            st.rerun()
