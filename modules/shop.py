"""SwimTrack Pro – Shop (Super Admin manages, others view)"""

import streamlit as st
import db


def render(conn):
    st.markdown("## 🛒 חנות")
    role = st.session_state.user_role

    if role == "super_admin":
        tab_view, tab_manage = st.tabs(["🛍️ תצוגת חנות", "⚙️ ניהול מוצרים"])
        with tab_view:
            _render_shop_view(conn)
        with tab_manage:
            _render_shop_manage(conn)
    else:
        _render_shop_view(conn)


def _render_shop_view(conn):
    st.markdown("### 🛍️ מוצרים")
    products = db.get_products(conn, active_only=True)

    if not products:
        st.info("אין מוצרים זמינים כרגע")
        return

    # Display in grid (3 per row)
    for i in range(0, len(products), 3):
        cols = st.columns(3)
        for j, p in enumerate(products[i:i+3]):
            with cols[j]:
                st.markdown(
                    f"""<div style='border:1px solid #ddd;border-radius:12px;
                        padding:16px;text-align:center;height:220px;
                        display:flex;flex-direction:column;justify-content:space-between'>
                        <div style='font-size:2rem'>🏊</div>
                        <div style='font-weight:bold;font-size:1rem'>{p['name']}</div>
                        <div style='font-size:0.85rem;color:#666'>{p['description'] or ''}</div>
                        <div style='font-size:1.1rem;color:#2196F3;font-weight:bold'>
                            {'₪' + str(p['price_ils']) if p['price_ils'] else 'ראה מחיר בקישור'}
                        </div>
                    </div>""",
                    unsafe_allow_html=True,
                )
                if p["external_link"]:
                    st.link_button(
                        "🔗 לרכישה (קישור חיצוני)",
                        p["external_link"],
                        use_container_width=True,
                    )
                else:
                    st.caption("אין קישור לרכישה")


def _render_shop_manage(conn):
    st.markdown("### ⚙️ ניהול מוצרים (סופר-מנהל)")

    # Add product
    with st.expander("➕ הוסף מוצר חדש", expanded=False):
        with st.form("add_product"):
            name = st.text_input("שם המוצר *")
            description = st.text_area("תיאור", height=80)
            price = st.number_input("מחיר (₪)", min_value=0.0, step=1.0)
            external_link = st.text_input("קישור לרכישה חיצוני", placeholder="https://...")
            image_url = st.text_input("URL תמונה (אופציונלי)", placeholder="https://...")
            submitted = st.form_submit_button("➕ הוסף מוצר", use_container_width=True)

        if submitted:
            if not name:
                st.error("שם המוצר הוא שדה חובה")
            else:
                db.create_product(
                    conn, name, description or None, price or None,
                    image_url or None, external_link or None,
                    st.session_state.user_id,
                )
                st.success(f"✅ המוצר '{name}' נוסף!")
                st.rerun()

    # Edit/deactivate products
    st.markdown("#### מוצרים קיימים")
    products = db.get_products(conn, active_only=False)
    if not products:
        st.info("אין מוצרים")
        return

    for p in products:
        status = "✅ פעיל" if p["active"] else "❌ לא פעיל"
        with st.expander(f"{p['name']}  |  {status}", expanded=False):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**תיאור:** {p['description'] or '—'}")
                st.write(f"**מחיר:** {'₪' + str(p['price_ils']) if p['price_ils'] else '—'}")
                st.write(f"**קישור:** {p['external_link'] or '—'}")
            with col2:
                if p["active"]:
                    if st.button("🔒 השבת", key=f"deact_{p['id']}"):
                        db.update_product(conn, p["id"], active=0)
                        st.rerun()
                else:
                    if st.button("✅ הפעל", key=f"act_{p['id']}"):
                        db.update_product(conn, p["id"], active=1)
                        st.rerun()
