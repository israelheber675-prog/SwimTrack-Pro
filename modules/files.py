"""SwimTrack Pro – File Manager (local & uploaded files)"""

import streamlit as st
import os
import shutil
import mimetypes
from pathlib import Path
from datetime import datetime
import db

UPLOADS_DIR = Path("uploads")
ALLOWED_EXT = {
    "תמונות":   [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"],
    "מסמכים":   [".pdf", ".docx", ".doc", ".txt", ".rtf"],
    "גיליונות": [".csv", ".xlsx", ".xls", ".tsv"],
    "וידאו":    [".mp4", ".avi", ".mov", ".mkv"],
    "שמע":      [".mp3", ".wav", ".m4a", ".ogg"],
    "אחר":      [],
}
ALL_ALLOWED = [ext for exts in ALLOWED_EXT.values() for ext in exts]
MAX_FILE_MB = 50


def _ensure_uploads():
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOADS_DIR / "images").mkdir(exist_ok=True)
    (UPLOADS_DIR / "docs").mkdir(exist_ok=True)
    (UPLOADS_DIR / "data").mkdir(exist_ok=True)
    (UPLOADS_DIR / "other").mkdir(exist_ok=True)


def _cat_for_ext(ext: str) -> str:
    ext = ext.lower()
    if ext in ALLOWED_EXT["תמונות"]:   return "images"
    if ext in ALLOWED_EXT["מסמכים"]:   return "docs"
    if ext in ALLOWED_EXT["גיליונות"]: return "data"
    return "other"


def render(conn):
    _ensure_uploads()
    st.markdown("## 📁 ניהול קבצים")

    tab_upload, tab_browse, tab_local = st.tabs(
        ["⬆️ העלאת קבצים", "📂 קבצים שהועלו", "💻 גישה לקבצים מהמכשיר"]
    )

    with tab_upload:
        _render_upload()
    with tab_browse:
        _render_browse()
    with tab_local:
        _render_local_access(conn)


# ─── Upload ───────────────────────────────────────────────────────────────────

def _render_upload():
    st.markdown("### ⬆️ העלאת קבצים מהמכשיר")
    st.caption(f"גדלים מותרים עד {MAX_FILE_MB} MB לקובץ")

    uploaded_files = st.file_uploader(
        "גרור קבצים לכאן או לחץ לבחירה",
        accept_multiple_files=True,
        type=None,   # allow all – we validate below
        key="main_uploader",
    )

    if not uploaded_files:
        st.info("טרם הועלו קבצים בסשן זה")
        return

    results = []
    for f in uploaded_files:
        size_mb = len(f.getvalue()) / (1024 * 1024)
        ext = Path(f.name).suffix.lower()
        cat = _cat_for_ext(ext)
        dest = UPLOADS_DIR / cat / f.name

        if size_mb > MAX_FILE_MB:
            results.append({"קובץ": f.name, "סטטוס": f"❌ גדול מדי ({size_mb:.1f} MB)", "גודל": f"{size_mb:.1f} MB"})
            continue

        # Save
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as out:
            out.write(f.getvalue())
        results.append({
            "קובץ": f.name,
            "סטטוס": "✅ הועלה",
            "גודל": f"{size_mb:.2f} MB",
            "קטגוריה": cat,
            "נתיב": str(dest),
        })

    if results:
        import pandas as pd
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Show images inline
        images = [r for r in results if r["סטטוס"] == "✅ הועלה" and r["קטגוריה"] == "images"]
        if images:
            st.markdown("#### תצוגה מקדימה")
            cols = st.columns(min(len(images), 4))
            for i, img_info in enumerate(images):
                with cols[i % 4]:
                    try:
                        st.image(img_info["נתיב"], caption=img_info["קובץ"], use_container_width=True)
                    except Exception:
                        st.caption(img_info["קובץ"])

        # CSV quick-view
        data_files = [r for r in results if r["סטטוס"] == "✅ הועלה" and r["קטגוריה"] == "data"]
        if data_files:
            st.markdown("#### תצוגה מקדימה – גיליון נתונים")
            for df_info in data_files[:1]:
                try:
                    import pandas as pd
                    if df_info["קובץ"].endswith(".csv"):
                        preview = pd.read_csv(df_info["נתיב"], encoding="utf-8-sig")
                    else:
                        preview = pd.read_excel(df_info["נתיב"])
                    st.dataframe(preview.head(20), use_container_width=True, hide_index=True)
                    st.caption(f"מוצגות 20 שורות ראשונות מתוך {len(preview)}")
                except Exception as e:
                    st.caption(f"לא ניתן להציג תצוגה מקדימה: {e}")


# ─── Browse Uploaded ──────────────────────────────────────────────────────────

def _render_browse():
    st.markdown("### 📂 קבצים שהועלו למערכת")

    cats = ["images", "docs", "data", "other"]
    cat_labels = {"images": "🖼️ תמונות", "docs": "📄 מסמכים",
                  "data": "📊 גיליונות", "other": "📎 אחר"}

    for cat in cats:
        cat_dir = UPLOADS_DIR / cat
        if not cat_dir.exists():
            continue
        files = sorted(cat_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            continue

        with st.expander(f"{cat_labels[cat]}  ({len(files)} קבצים)", expanded=False):
            for fp in files:
                size_mb = fp.stat().st_size / (1024 * 1024)
                mtime = datetime.fromtimestamp(fp.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                with col1:
                    st.write(fp.name)
                with col2:
                    st.caption(f"{size_mb:.2f} MB")
                with col3:
                    st.caption(mtime)
                with col4:
                    with open(fp, "rb") as fh:
                        st.download_button(
                            "⬇️",
                            fh.read(),
                            file_name=fp.name,
                            key=f"dl_{fp.name}",
                        )

            # Show image gallery
            if cat == "images":
                img_files = [f for f in files if f.suffix.lower() in [".jpg",".jpeg",".png",".webp",".gif"]]
                if img_files:
                    cols = st.columns(min(4, len(img_files)))
                    for i, imgf in enumerate(img_files[:8]):
                        with cols[i % 4]:
                            try:
                                st.image(str(imgf), caption=imgf.name, use_container_width=True)
                            except Exception:
                                pass


# ─── Local File Access ────────────────────────────────────────────────────────

def _render_local_access(conn):
    st.markdown("### 💻 גישה לקבצים מהמכשיר")
    st.info(
        "מכיוון שהאפליקציה רצה **מקומית על המחשב שלך**, "
        "ניתן לגשת ישירות לקבצים לפי נתיב."
    )

    tab_browse_local, tab_import = st.tabs(
        ["🗂️ דפדוף בתיקיות", "📥 ייבוא ישיר לסילבוס / תלמידים"]
    )

    with tab_browse_local:
        _render_local_browser()
    with tab_import:
        _render_local_import(conn)


def _render_local_browser():
    st.markdown("#### 🗂️ דפדוף בתיקיות")

    default_path = str(Path.home())
    folder_path = st.text_input(
        "נתיב תיקייה",
        value=default_path,
        placeholder=r"C:\Users\שם\Documents",
        key="local_browser_path",
    )

    if st.button("📂 פתח תיקייה", key="open_folder"):
        st.session_state["browser_path"] = folder_path

    browse_path = st.session_state.get("browser_path", default_path)

    try:
        p = Path(browse_path)
        if not p.exists():
            st.error("הנתיב לא קיים")
            return
        if not p.is_dir():
            st.error("הנתיב אינו תיקייה")
            return

        items = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        dirs  = [i for i in items if i.is_dir()]
        files = [i for i in items if i.is_file()]

        st.caption(f"📂 {browse_path}  |  {len(dirs)} תיקיות, {len(files)} קבצים")

        # Parent dir button
        if p.parent != p:
            if st.button("⬆️ תיקייה קודמת"):
                st.session_state["browser_path"] = str(p.parent)
                st.rerun()

        col1, col2 = st.columns(2)

        with col1:
            if dirs:
                st.markdown("**📁 תיקיות**")
                for d in dirs[:30]:
                    if st.button(f"📁 {d.name}", key=f"dir_{d.name}", use_container_width=True):
                        st.session_state["browser_path"] = str(d)
                        st.rerun()

        with col2:
            if files:
                st.markdown("**📄 קבצים**")
                import pandas as pd
                file_rows = []
                for f in files[:50]:
                    size_kb = f.stat().st_size / 1024
                    file_rows.append({
                        "שם": f.name,
                        "גודל": f"{size_kb:.1f} KB",
                        "סוג": f.suffix,
                    })
                st.dataframe(pd.DataFrame(file_rows), use_container_width=True, hide_index=True)

        # Quick-open a file
        st.divider()
        file_path_input = st.text_input(
            "נתיב לקובץ ספציפי לתצוגה / ייבוא",
            placeholder=r"C:\Users\...\file.csv",
            key="local_file_path",
        )
        if file_path_input and st.button("👁️ הצג קובץ"):
            _preview_local_file(file_path_input)

    except PermissionError:
        st.error("❌ אין הרשאת גישה לתיקייה זו")
    except Exception as e:
        st.error(f"שגיאה: {e}")


def _preview_local_file(file_path: str):
    p = Path(file_path)
    if not p.exists():
        st.error("הקובץ לא נמצא")
        return

    ext = p.suffix.lower()
    size_mb = p.stat().st_size / (1024 * 1024)

    st.markdown(f"**{p.name}**  |  {size_mb:.2f} MB")

    if ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"]:
        try:
            st.image(file_path, use_container_width=True)
        except Exception as e:
            st.error(f"לא ניתן להציג תמונה: {e}")

    elif ext in [".csv", ".tsv"]:
        try:
            import pandas as pd
            sep = "\t" if ext == ".tsv" else ","
            df = pd.read_csv(file_path, sep=sep, encoding="utf-8-sig", errors="replace")
            st.dataframe(df.head(30), use_container_width=True, hide_index=True)
            st.caption(f"{len(df)} שורות")
        except Exception as e:
            st.error(f"שגיאה בפתיחת CSV: {e}")

    elif ext in [".xlsx", ".xls"]:
        try:
            import pandas as pd
            df = pd.read_excel(file_path)
            st.dataframe(df.head(30), use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"שגיאה: {e}")

    elif ext == ".txt":
        try:
            with open(file_path, encoding="utf-8", errors="replace") as fh:
                text = fh.read(5000)
            st.text_area("תוכן הקובץ (5000 תווים ראשונים)", text, height=300)
        except Exception as e:
            st.error(f"שגיאה: {e}")

    elif ext == ".pdf":
        st.info("קובץ PDF – ניתן להוריד בלבד")
        with open(file_path, "rb") as fh:
            st.download_button("⬇️ הורד PDF", fh.read(), file_name=p.name)

    else:
        try:
            with open(file_path, "rb") as fh:
                st.download_button("⬇️ הורד קובץ", fh.read(), file_name=p.name)
        except Exception as e:
            st.error(f"שגיאה: {e}")


def _render_local_import(conn):
    st.markdown("#### 📥 ייבוא מקובץ מקומי")

    import_type = st.selectbox(
        "מה לייבא?",
        ["📚 סילבוס מקובץ CSV/TXT", "🎓 תלמידים מקובץ CSV"],
    )

    file_path = st.text_input(
        "נתיב מלא לקובץ",
        placeholder=r"C:\Users\...\syllabus.csv",
        key="import_local_path",
    )

    if not file_path:
        return

    p = Path(file_path)
    if not p.exists():
        st.error("הקובץ לא נמצא בנתיב זה")
        return

    if import_type.startswith("📚"):
        _import_syllabus_from_path(conn, p)
    else:
        _import_students_from_path(conn, p)


def _import_syllabus_from_path(conn, p: Path):
    from modules.syllabus import _parse_csv_content
    existing_subjects = db.get_subjects(conn)

    subject_name = st.text_input("שם הנושא", placeholder="שחייה / רכיבה...", key="imp_sub")
    replace = False
    if subject_name and subject_name in existing_subjects:
        replace = st.checkbox(f"החלף סילבוס קיים של '{subject_name}'")

    if st.button("📥 ייבא", type="primary") and subject_name:
        try:
            with open(p, encoding="utf-8-sig", errors="replace") as fh:
                content = fh.read()
            parsed = _parse_csv_content(content)
            if not parsed:
                st.error("לא ניתן לנתח. בדוק פורמט.")
                return
            if replace:
                conn.execute("DELETE FROM syllabus WHERE subject=?", (subject_name,))
                conn.commit()
            for phase, task, order_num in parsed:
                db.add_custom_syllabus(conn, subject_name, phase, task, order_num)
            action = "עודכן" if replace else "נוסף"
            st.success(f"✅ סילבוס '{subject_name}' {action} – {len(parsed)} משימות")
            st.rerun()
        except Exception as e:
            st.error(f"שגיאה: {e}")


def _import_students_from_path(conn, p: Path):
    import pandas as pd

    groups = db.get_groups(conn)
    if not groups:
        st.warning("אין קבוצות. צרו קבוצה קודם.")
        return

    group_map = {g["name"]: g["id"] for g in groups}
    sel_grp = st.selectbox("קבוצה לשיוך", list(group_map.keys()), key="imp_grp")

    if st.button("📥 ייבא תלמידים", type="primary"):
        try:
            df = pd.read_csv(str(p), encoding="utf-8-sig", errors="replace")
            df.columns = [c.strip() for c in df.columns]

            # Expected columns (flexible):
            col_map = {
                "name": ["name", "שם", "שם מלא"],
                "phone": ["phone", "טלפון"],
                "email": ["email", "אימייל"],
                "parent_name": ["parent_name", "הורה", "שם הורה"],
                "parent_phone": ["parent_phone", "טלפון הורה"],
                "credits": ["credits", "קרדיטים"],
            }

            def find_col(df_cols, aliases):
                for a in aliases:
                    if a in df_cols:
                        return a
                return None

            added = 0
            errors = []
            for _, row in df.iterrows():
                name_col = find_col(df.columns, col_map["name"])
                if not name_col or not str(row.get(name_col, "")).strip():
                    continue
                name = str(row[name_col]).strip()

                def g(aliases):
                    c = find_col(df.columns, aliases)
                    return str(row[c]).strip() if c and str(row[c]).strip() not in ("nan", "") else None

                try:
                    db.create_student(
                        conn, name,
                        g(col_map["email"]),
                        g(col_map["phone"]),
                        g(col_map["parent_name"]),
                        g(col_map["parent_phone"]),
                        None, None,
                        group_map[sel_grp],
                        float(g(col_map["credits"]) or 10),
                    )
                    added += 1
                except Exception as e:
                    errors.append(f"{name}: {e}")

            st.success(f"✅ נוספו {added} תלמידים לקבוצה '{sel_grp}'")
            if errors:
                with st.expander(f"⚠️ {len(errors)} שגיאות"):
                    for e in errors:
                        st.caption(e)
            st.rerun()

        except Exception as e:
            st.error(f"שגיאה בקריאת הקובץ: {e}")
