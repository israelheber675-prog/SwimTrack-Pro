"""SwimTrack Pro – Database layer (SQLite)"""

import sqlite3
import hashlib
import os
import secrets
from datetime import datetime, date, timedelta
from config import DB_PATH, SWIMMING_SYLLABUS, DATA_RETENTION_YEARS, PRE_SEEDED_ADMINS


# ─── Connection ───────────────────────────────────────────────────────────────

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


# ─── Password helpers ─────────────────────────────────────────────────────────

def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return h, salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    h, _ = hash_password(password, salt)
    return h == stored_hash


# ─── Schema init ──────────────────────────────────────────────────────────────

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        name             TEXT NOT NULL,
        email            TEXT UNIQUE,
        phone            TEXT UNIQUE,
        password_hash    TEXT NOT NULL,
        salt             TEXT NOT NULL,
        role             TEXT NOT NULL DEFAULT 'instructor',
        is_active        INTEGER NOT NULL DEFAULT 1,
        first_login_done INTEGER NOT NULL DEFAULT 0,
        belongs_to_manager_id INTEGER,
        created_at       TEXT NOT NULL,
        FOREIGN KEY(belongs_to_manager_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS groups (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        subject     TEXT NOT NULL DEFAULT 'שחייה',
        manager_id  INTEGER,
        instructor_id INTEGER,
        archived    INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT NOT NULL,
        archived_at TEXT,
        FOREIGN KEY(manager_id) REFERENCES users(id),
        FOREIGN KEY(instructor_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS students (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        name            TEXT NOT NULL,
        email           TEXT,
        phone           TEXT,
        parent_name     TEXT,
        parent_phone    TEXT,
        birth_date      TEXT,
        notes           TEXT,
        group_id        INTEGER,
        credits         REAL NOT NULL DEFAULT 0,
        level_color     TEXT NOT NULL DEFAULT 'לא התחיל',
        created_at      TEXT NOT NULL,
        FOREIGN KEY(group_id) REFERENCES groups(id)
    );

    CREATE TABLE IF NOT EXISTS sessions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id        INTEGER NOT NULL,
        session_date    TEXT NOT NULL,
        instructor_id   INTEGER,
        notes           TEXT,
        created_at      TEXT NOT NULL,
        FOREIGN KEY(group_id) REFERENCES groups(id),
        FOREIGN KEY(instructor_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS attendance (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id  INTEGER NOT NULL,
        student_id  INTEGER NOT NULL,
        present     INTEGER NOT NULL DEFAULT 0,
        credit_deducted INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT NOT NULL,
        FOREIGN KEY(session_id) REFERENCES sessions(id),
        FOREIGN KEY(student_id) REFERENCES students(id),
        UNIQUE(session_id, student_id)
    );

    CREATE TABLE IF NOT EXISTS syllabus (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        subject     TEXT NOT NULL,
        phase_name  TEXT NOT NULL,
        subtask     TEXT NOT NULL,
        order_num   INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS student_progress (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id  INTEGER NOT NULL,
        subtask_id  INTEGER NOT NULL,
        color       TEXT NOT NULL DEFAULT 'לא התחיל',
        updated_by  INTEGER,
        updated_at  TEXT NOT NULL,
        FOREIGN KEY(student_id) REFERENCES students(id),
        FOREIGN KEY(subtask_id) REFERENCES syllabus(id),
        UNIQUE(student_id, subtask_id)
    );

    CREATE TABLE IF NOT EXISTS chat_messages (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id   INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,
        message     TEXT NOT NULL,
        sent_at     TEXT NOT NULL,
        blocked     INTEGER NOT NULL DEFAULT 0,
        block_reason TEXT,
        read_at     TEXT,
        FOREIGN KEY(sender_id) REFERENCES users(id),
        FOREIGN KEY(receiver_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS clock_records (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL,
        clock_in    TEXT NOT NULL,
        clock_out   TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS signatures (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id      INTEGER NOT NULL,
        parent_name     TEXT NOT NULL,
        signature_data  TEXT NOT NULL,
        declaration_text TEXT,
        signed_at       TEXT NOT NULL,
        FOREIGN KEY(student_id) REFERENCES students(id)
    );

    CREATE TABLE IF NOT EXISTS shop_products (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        name            TEXT NOT NULL,
        description     TEXT,
        price_ils       REAL,
        image_url       TEXT,
        external_link   TEXT,
        active          INTEGER NOT NULL DEFAULT 1,
        created_by      INTEGER,
        created_at      TEXT NOT NULL,
        FOREIGN KEY(created_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS inventory_items (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        category    TEXT NOT NULL DEFAULT 'כללי',
        quantity    INTEGER NOT NULL DEFAULT 0,
        notes       TEXT,
        updated_at  TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS feedback_notes (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user_id INTEGER NOT NULL,
        to_user_id  INTEGER NOT NULL,
        note        TEXT NOT NULL,
        created_at  TEXT NOT NULL,
        read_at     TEXT,
        FOREIGN KEY(from_user_id) REFERENCES users(id),
        FOREIGN KEY(to_user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS lane_assignments (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id  INTEGER NOT NULL,
        student_id  INTEGER NOT NULL,
        lane_number INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY(session_id) REFERENCES sessions(id),
        FOREIGN KEY(student_id) REFERENCES students(id),
        UNIQUE(session_id, student_id)
    );

    CREATE TABLE IF NOT EXISTS system_alerts (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_type      TEXT NOT NULL,
        message         TEXT NOT NULL,
        related_user_id INTEGER,
        created_at      TEXT NOT NULL,
        acknowledged    INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(related_user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS dry_statistics (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        stat_date   TEXT NOT NULL,
        stat_key    TEXT NOT NULL,
        stat_value  REAL NOT NULL,
        notes       TEXT
    );
    """)

    conn.commit()

    # Migration: add belongs_to_manager_id if missing (for existing DBs)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "belongs_to_manager_id" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN belongs_to_manager_id INTEGER")
        conn.commit()

    _seed_syllabus(conn)
    _seed_pre_admins(conn)
    conn.close()


def _seed_syllabus(conn):
    """Seed or re-seed the swimming syllabus if counts don't match."""
    c = conn.cursor()
    expected = sum(len(v) for v in SWIMMING_SYLLABUS.values())
    c.execute("SELECT COUNT(*) FROM syllabus WHERE subject='שחייה'")
    existing = c.fetchone()[0]
    if existing == expected:
        return  # Already up to date
    # Replace with updated syllabus
    c.execute("DELETE FROM syllabus WHERE subject='שחייה'")
    order = 0
    for phase, tasks in SWIMMING_SYLLABUS.items():
        for task in tasks:
            c.execute(
                "INSERT INTO syllabus (subject, phase_name, subtask, order_num) VALUES (?,?,?,?)",
                ("שחייה", phase, task, order),
            )
            order += 1
    conn.commit()


def _seed_pre_admins(conn):
    """Create pre-configured super admin accounts if they don't exist yet."""
    if not PRE_SEEDED_ADMINS:
        return
    now = datetime.now().isoformat()
    for admin in PRE_SEEDED_ADMINS:
        existing = conn.execute(
            "SELECT id FROM users WHERE email=?", (admin["email"],)
        ).fetchone()
        if existing:
            # Ensure role is super_admin
            conn.execute("UPDATE users SET role='super_admin' WHERE email=?", (admin["email"],))
        else:
            h, salt = hash_password(admin["password"])
            conn.execute(
                """INSERT INTO users (name,email,password_hash,salt,role,created_at)
                   VALUES (?,?,?,?,'super_admin',?)""",
                (admin["name"], admin["email"], h, salt, now),
            )
    conn.commit()


# ─── Users ────────────────────────────────────────────────────────────────────

def count_users(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def create_user(conn, name, email, phone, password, role=None, belongs_to_manager_id=None) -> int:
    now = datetime.now().isoformat()
    h, salt = hash_password(password)
    user_count = count_users(conn)
    if user_count < 2:
        assigned_role = "super_admin"
    else:
        assigned_role = role or "instructor"
    conn.execute(
        """INSERT INTO users
           (name,email,phone,password_hash,salt,role,belongs_to_manager_id,created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (name, email or None, phone or None, h, salt, assigned_role, belongs_to_manager_id, now),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_user_by_login(conn, identifier: str):
    """Find user by email or phone."""
    return conn.execute(
        "SELECT * FROM users WHERE (email=? OR phone=?) AND is_active=1",
        (identifier, identifier),
    ).fetchone()


def get_user(conn, user_id: int):
    return conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()


def get_all_users(conn):
    return conn.execute("SELECT * FROM users WHERE is_active=1 ORDER BY role,name").fetchall()


def get_users_by_role(conn, role: str):
    return conn.execute(
        "SELECT * FROM users WHERE role=? AND is_active=1 ORDER BY name", (role,)
    ).fetchall()


def mark_first_login(conn, user_id: int):
    conn.execute("UPDATE users SET first_login_done=1 WHERE id=?", (user_id,))
    conn.commit()


def update_user_role(conn, user_id: int, role: str):
    conn.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
    conn.commit()


def deactivate_user(conn, user_id: int):
    conn.execute("UPDATE users SET is_active=0 WHERE id=?", (user_id,))
    conn.commit()


# ─── Groups ───────────────────────────────────────────────────────────────────

def create_group(conn, name, subject, manager_id, instructor_id=None) -> int:
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO groups (name,subject,manager_id,instructor_id,created_at) VALUES (?,?,?,?,?)",
        (name, subject, manager_id, instructor_id, now),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_groups(conn, include_archived=False):
    if include_archived:
        return conn.execute("SELECT * FROM groups ORDER BY archived, name").fetchall()
    return conn.execute("SELECT * FROM groups WHERE archived=0 ORDER BY name").fetchall()


def get_group(conn, group_id: int):
    return conn.execute("SELECT * FROM groups WHERE id=?", (group_id,)).fetchone()


def archive_group(conn, group_id: int):
    conn.execute(
        "UPDATE groups SET archived=1, archived_at=? WHERE id=?",
        (datetime.now().isoformat(), group_id),
    )
    conn.commit()


def update_group(conn, group_id, name=None, instructor_id=None):
    if name:
        conn.execute("UPDATE groups SET name=? WHERE id=?", (name, group_id))
    if instructor_id is not None:
        conn.execute("UPDATE groups SET instructor_id=? WHERE id=?", (instructor_id, group_id))
    conn.commit()


# ─── Students ─────────────────────────────────────────────────────────────────

def create_student(conn, name, email, phone, parent_name, parent_phone,
                   birth_date, notes, group_id, credits=0) -> int:
    now = datetime.now().isoformat()
    conn.execute(
        """INSERT INTO students
           (name,email,phone,parent_name,parent_phone,birth_date,notes,group_id,credits,created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (name, email, phone, parent_name, parent_phone, birth_date, notes, group_id, credits, now),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_students(conn, group_id=None):
    if group_id:
        return conn.execute(
            "SELECT * FROM students WHERE group_id=? ORDER BY name", (group_id,)
        ).fetchall()
    return conn.execute("SELECT * FROM students ORDER BY name").fetchall()


def get_student(conn, student_id: int):
    return conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()


def update_student(conn, student_id, **kwargs):
    allowed = {"name","email","phone","parent_name","parent_phone","birth_date","notes","group_id","credits","level_color"}
    sets = []
    vals = []
    for k, v in kwargs.items():
        if k in allowed:
            sets.append(f"{k}=?")
            vals.append(v)
    if not sets:
        return
    vals.append(student_id)
    conn.execute(f"UPDATE students SET {', '.join(sets)} WHERE id=?", vals)
    conn.commit()


def add_credits(conn, student_id: int, amount: float):
    conn.execute("UPDATE students SET credits=credits+? WHERE id=?", (amount, student_id))
    conn.commit()


def deduct_credit(conn, student_id: int) -> bool:
    s = get_student(conn, student_id)
    if s is None:
        return False
    conn.execute("UPDATE students SET credits=credits-1 WHERE id=?", (student_id,))
    conn.commit()
    return True


def search_students(conn, query: str):
    q = f"%{query}%"
    return conn.execute(
        """SELECT * FROM students
           WHERE name LIKE ? OR email LIKE ? OR phone LIKE ?
              OR parent_name LIKE ? OR level_color LIKE ? OR notes LIKE ?
           ORDER BY name""",
        (q, q, q, q, q, q),
    ).fetchall()


def delete_old_student_data(conn):
    """Delete personal data older than DATA_RETENTION_YEARS (keep dry stats)."""
    cutoff = (datetime.now() - timedelta(days=DATA_RETENTION_YEARS * 365)).isoformat()
    # Save dry stat before deleting
    count = conn.execute(
        "SELECT COUNT(*) FROM students WHERE created_at < ?", (cutoff,)
    ).fetchone()[0]
    if count:
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO dry_statistics (stat_date,stat_key,stat_value,notes) VALUES (?,?,?,?)",
            (now, "deleted_students", count, f"Auto-deleted after {DATA_RETENTION_YEARS} years"),
        )
        conn.execute("DELETE FROM students WHERE created_at < ?", (cutoff,))
        conn.commit()


# ─── Sessions & Attendance ────────────────────────────────────────────────────

def create_session(conn, group_id, session_date, instructor_id, notes="") -> int:
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO sessions (group_id,session_date,instructor_id,notes,created_at) VALUES (?,?,?,?,?)",
        (group_id, session_date, instructor_id, notes, now),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_sessions(conn, group_id=None):
    if group_id:
        return conn.execute(
            "SELECT * FROM sessions WHERE group_id=? ORDER BY session_date DESC", (group_id,)
        ).fetchall()
    return conn.execute("SELECT * FROM sessions ORDER BY session_date DESC").fetchall()


def get_session(conn, session_id: int):
    return conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()


def upsert_attendance(conn, session_id, student_id, present: bool):
    now = datetime.now().isoformat()
    existing = conn.execute(
        "SELECT * FROM attendance WHERE session_id=? AND student_id=?",
        (session_id, student_id),
    ).fetchone()

    was_present = existing and existing["present"]
    is_present = int(present)

    if existing:
        conn.execute(
            "UPDATE attendance SET present=? WHERE session_id=? AND student_id=?",
            (is_present, session_id, student_id),
        )
    else:
        conn.execute(
            "INSERT INTO attendance (session_id,student_id,present,created_at) VALUES (?,?,?,?)",
            (session_id, student_id, is_present, now),
        )

    # Deduct credit when marking present (only once per record)
    if is_present and not was_present:
        deduct_credit(conn, student_id)
        conn.execute(
            "UPDATE attendance SET credit_deducted=1 WHERE session_id=? AND student_id=?",
            (session_id, student_id),
        )
    elif not is_present and was_present:
        # Restore credit
        conn.execute(
            "UPDATE students SET credits=credits+1 WHERE id=?", (student_id,)
        )
        conn.execute(
            "UPDATE attendance SET credit_deducted=0 WHERE session_id=? AND student_id=?",
            (session_id, student_id),
        )

    conn.commit()


def get_attendance(conn, session_id: int):
    return conn.execute(
        "SELECT * FROM attendance WHERE session_id=?", (session_id,)
    ).fetchall()


def get_student_attendance_history(conn, student_id: int):
    return conn.execute(
        """SELECT a.*, s.session_date, g.name as group_name
           FROM attendance a
           JOIN sessions s ON a.session_id=s.id
           JOIN groups g ON s.group_id=g.id
           WHERE a.student_id=?
           ORDER BY s.session_date DESC""",
        (student_id,),
    ).fetchall()


# ─── Lane Assignments ─────────────────────────────────────────────────────────

def upsert_lane(conn, session_id, student_id, lane_number):
    existing = conn.execute(
        "SELECT id FROM lane_assignments WHERE session_id=? AND student_id=?",
        (session_id, student_id),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE lane_assignments SET lane_number=? WHERE session_id=? AND student_id=?",
            (lane_number, session_id, student_id),
        )
    else:
        conn.execute(
            "INSERT INTO lane_assignments (session_id,student_id,lane_number) VALUES (?,?,?)",
            (session_id, student_id, lane_number),
        )
    conn.commit()


def get_lane_assignments(conn, session_id):
    return conn.execute(
        """SELECT la.*, s.name as student_name, s.level_color
           FROM lane_assignments la
           JOIN students s ON la.student_id=s.id
           WHERE la.session_id=?
           ORDER BY la.lane_number, s.name""",
        (session_id,),
    ).fetchall()


# ─── Syllabus & Progress ──────────────────────────────────────────────────────

def get_syllabus(conn, subject="שחייה"):
    return conn.execute(
        "SELECT * FROM syllabus WHERE subject=? ORDER BY order_num", (subject,)
    ).fetchall()


def get_subjects(conn):
    rows = conn.execute("SELECT DISTINCT subject FROM syllabus ORDER BY subject").fetchall()
    return [r["subject"] for r in rows]


def add_custom_syllabus(conn, subject, phase_name, subtask, order_num):
    conn.execute(
        "INSERT INTO syllabus (subject,phase_name,subtask,order_num) VALUES (?,?,?,?)",
        (subject, phase_name, subtask, order_num),
    )
    conn.commit()


def get_student_progress(conn, student_id):
    return conn.execute(
        "SELECT * FROM student_progress WHERE student_id=?", (student_id,)
    ).fetchall()


def upsert_progress(conn, student_id, subtask_id, color, updated_by):
    now = datetime.now().isoformat()
    existing = conn.execute(
        "SELECT id FROM student_progress WHERE student_id=? AND subtask_id=?",
        (student_id, subtask_id),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE student_progress SET color=?,updated_by=?,updated_at=? WHERE student_id=? AND subtask_id=?",
            (color, updated_by, now, student_id, subtask_id),
        )
    else:
        conn.execute(
            "INSERT INTO student_progress (student_id,subtask_id,color,updated_by,updated_at) VALUES (?,?,?,?,?)",
            (student_id, subtask_id, color, updated_by, now),
        )
    conn.commit()


# ─── Chat ─────────────────────────────────────────────────────────────────────

def send_message(conn, sender_id, receiver_id, message, blocked=False, block_reason=None):
    now = datetime.now().isoformat()
    conn.execute(
        """INSERT INTO chat_messages (sender_id,receiver_id,message,sent_at,blocked,block_reason)
           VALUES (?,?,?,?,?,?)""",
        (sender_id, receiver_id, message, now, int(blocked), block_reason),
    )
    conn.commit()


def get_messages(conn, user_id):
    """Get all messages where user is sender or receiver (excluding blocked)."""
    return conn.execute(
        """SELECT m.*, u1.name as sender_name, u2.name as receiver_name
           FROM chat_messages m
           JOIN users u1 ON m.sender_id=u1.id
           JOIN users u2 ON m.receiver_id=u2.id
           WHERE (m.sender_id=? OR m.receiver_id=?) AND m.blocked=0
           ORDER BY m.sent_at DESC""",
        (user_id, user_id),
    ).fetchall()


def get_conversation(conn, user_a, user_b):
    return conn.execute(
        """SELECT m.*, u1.name as sender_name
           FROM chat_messages m
           JOIN users u1 ON m.sender_id=u1.id
           WHERE ((m.sender_id=? AND m.receiver_id=?) OR (m.sender_id=? AND m.receiver_id=?))
             AND m.blocked=0
           ORDER BY m.sent_at ASC""",
        (user_a, user_b, user_b, user_a),
    ).fetchall()


def mark_messages_read(conn, receiver_id, sender_id):
    now = datetime.now().isoformat()
    conn.execute(
        "UPDATE chat_messages SET read_at=? WHERE receiver_id=? AND sender_id=? AND read_at IS NULL",
        (now, receiver_id, sender_id),
    )
    conn.commit()


def get_unread_count(conn, user_id):
    return conn.execute(
        "SELECT COUNT(*) FROM chat_messages WHERE receiver_id=? AND read_at IS NULL AND blocked=0",
        (user_id,),
    ).fetchone()[0]


# ─── Feedback Notes ───────────────────────────────────────────────────────────

def add_feedback(conn, from_user_id, to_user_id, note):
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO feedback_notes (from_user_id,to_user_id,note,created_at) VALUES (?,?,?,?)",
        (from_user_id, to_user_id, note, now),
    )
    conn.commit()


def get_feedback_for_user(conn, user_id):
    return conn.execute(
        """SELECT f.*, u.name as from_name
           FROM feedback_notes f JOIN users u ON f.from_user_id=u.id
           WHERE f.to_user_id=? ORDER BY f.created_at DESC""",
        (user_id,),
    ).fetchall()


# ─── Clock ────────────────────────────────────────────────────────────────────

def clock_in(conn, user_id) -> int:
    # Check if already clocked in
    open_rec = conn.execute(
        "SELECT id FROM clock_records WHERE user_id=? AND clock_out IS NULL", (user_id,)
    ).fetchone()
    if open_rec:
        return open_rec["id"]
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO clock_records (user_id,clock_in) VALUES (?,?)", (user_id, now)
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def clock_out(conn, user_id):
    now = datetime.now().isoformat()
    conn.execute(
        "UPDATE clock_records SET clock_out=? WHERE user_id=? AND clock_out IS NULL",
        (now, user_id),
    )
    conn.commit()


def get_clock_records(conn, user_id=None):
    if user_id:
        return conn.execute(
            "SELECT * FROM clock_records WHERE user_id=? ORDER BY clock_in DESC", (user_id,)
        ).fetchall()
    return conn.execute(
        """SELECT cr.*, u.name as user_name
           FROM clock_records cr JOIN users u ON cr.user_id=u.id
           ORDER BY cr.clock_in DESC""",
    ).fetchall()


def is_clocked_in(conn, user_id) -> bool:
    r = conn.execute(
        "SELECT id FROM clock_records WHERE user_id=? AND clock_out IS NULL", (user_id,)
    ).fetchone()
    return r is not None


# ─── Signatures ───────────────────────────────────────────────────────────────

def save_signature(conn, student_id, parent_name, signature_data, declaration_text):
    now = datetime.now().isoformat()
    conn.execute(
        """INSERT INTO signatures (student_id,parent_name,signature_data,declaration_text,signed_at)
           VALUES (?,?,?,?,?)""",
        (student_id, parent_name, signature_data, declaration_text, now),
    )
    conn.commit()


def get_latest_signature(conn, student_id):
    return conn.execute(
        "SELECT * FROM signatures WHERE student_id=? ORDER BY signed_at DESC LIMIT 1",
        (student_id,),
    ).fetchone()


def signature_valid(conn, student_id) -> bool:
    sig = get_latest_signature(conn, student_id)
    if not sig:
        return False
    signed = datetime.fromisoformat(sig["signed_at"])
    return (datetime.now() - signed).days < 365


# ─── Shop ─────────────────────────────────────────────────────────────────────

def create_product(conn, name, description, price_ils, image_url, external_link, created_by) -> int:
    now = datetime.now().isoformat()
    conn.execute(
        """INSERT INTO shop_products (name,description,price_ils,image_url,external_link,created_by,created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (name, description, price_ils, image_url, external_link, created_by, now),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_products(conn, active_only=True):
    if active_only:
        return conn.execute(
            "SELECT * FROM shop_products WHERE active=1 ORDER BY name"
        ).fetchall()
    return conn.execute("SELECT * FROM shop_products ORDER BY name").fetchall()


def update_product(conn, product_id, **kwargs):
    allowed = {"name","description","price_ils","image_url","external_link","active"}
    sets = []
    vals = []
    for k, v in kwargs.items():
        if k in allowed:
            sets.append(f"{k}=?")
            vals.append(v)
    if sets:
        vals.append(product_id)
        conn.execute(f"UPDATE shop_products SET {', '.join(sets)} WHERE id=?", vals)
        conn.commit()


# ─── Inventory ────────────────────────────────────────────────────────────────

def upsert_inventory(conn, name, category, quantity, notes=""):
    now = datetime.now().isoformat()
    existing = conn.execute(
        "SELECT id FROM inventory_items WHERE name=? AND category=?", (name, category)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE inventory_items SET quantity=?,notes=?,updated_at=? WHERE id=?",
            (quantity, notes, now, existing["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO inventory_items (name,category,quantity,notes,updated_at) VALUES (?,?,?,?,?)",
            (name, category, quantity, notes, now),
        )
    conn.commit()


def get_inventory(conn, category=None):
    if category:
        return conn.execute(
            "SELECT * FROM inventory_items WHERE category=? ORDER BY name", (category,)
        ).fetchall()
    return conn.execute("SELECT * FROM inventory_items ORDER BY category,name").fetchall()


def get_inventory_categories(conn):
    rows = conn.execute(
        "SELECT DISTINCT category FROM inventory_items ORDER BY category"
    ).fetchall()
    return [r["category"] for r in rows]


def delete_inventory_item(conn, item_id):
    conn.execute("DELETE FROM inventory_items WHERE id=?", (item_id,))
    conn.commit()


# ─── Alerts ───────────────────────────────────────────────────────────────────

def create_alert(conn, alert_type, message, related_user_id=None):
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO system_alerts (alert_type,message,related_user_id,created_at) VALUES (?,?,?,?)",
        (alert_type, message, related_user_id, now),
    )
    conn.commit()


def get_alerts(conn, unacknowledged_only=True):
    if unacknowledged_only:
        return conn.execute(
            "SELECT * FROM system_alerts WHERE acknowledged=0 ORDER BY created_at DESC"
        ).fetchall()
    return conn.execute(
        "SELECT * FROM system_alerts ORDER BY created_at DESC"
    ).fetchall()


def acknowledge_alert(conn, alert_id):
    conn.execute(
        "UPDATE system_alerts SET acknowledged=1 WHERE id=?", (alert_id,)
    )
    conn.commit()


# ─── Statistics (Dry) ─────────────────────────────────────────────────────────

def get_dashboard_stats(conn):
    stats = {}
    stats["total_students"] = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    stats["active_groups"] = conn.execute("SELECT COUNT(*) FROM groups WHERE archived=0").fetchone()[0]
    stats["total_sessions"] = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    stats["total_users"] = conn.execute("SELECT COUNT(*) FROM users WHERE is_active=1").fetchone()[0]

    today = date.today().isoformat()
    stats["sessions_today"] = conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE session_date=?", (today,)
    ).fetchone()[0]

    stats["low_credit_students"] = conn.execute(
        "SELECT COUNT(*) FROM students WHERE credits <= 1"
    ).fetchone()[0]

    stats["pending_signatures"] = conn.execute(
        """SELECT COUNT(*) FROM students s
           WHERE NOT EXISTS (
               SELECT 1 FROM signatures sig WHERE sig.student_id=s.id
               AND julianday('now') - julianday(sig.signed_at) < 365
           )"""
    ).fetchone()[0]

    stats["unread_alerts"] = conn.execute(
        "SELECT COUNT(*) FROM system_alerts WHERE acknowledged=0"
    ).fetchone()[0]

    return stats
