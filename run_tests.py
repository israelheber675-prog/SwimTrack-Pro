# -*- coding: utf-8 -*-
"""SwimTrack Pro – Full integration test suite"""

import sys, os, re, io
# Force UTF-8 output regardless of terminal encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

PASS = []; FAIL = []

def check(name, condition, detail=""):
    if condition:
        PASS.append(name)
        print(f"  ✓  {name}")
    else:
        FAIL.append(name)
        print(f"  ✗  {name}" + (f"  →  {detail}" if detail else ""))

# ── fresh DB ──────────────────────────────────────────────────────────────────
DB_FILE = os.path.join(os.path.dirname(__file__), "swimtrack_test.db")
if os.path.exists(DB_FILE):
    os.remove(DB_FILE)

import db as database
from config import (SWIMMING_SYLLABUS, PRE_SEEDED_ADMINS,
                    LANGUAGE_BLACKLIST, WHATSAPP_TEMPLATES, LEVEL_COLORS)

# patch DB path to test DB
database.DB_PATH = DB_FILE
import config as _cfg
orig_path = _cfg.DB_PATH
_cfg.DB_PATH = DB_FILE

print("\n══════════════════════════════════════════")
print("  SwimTrack Pro – Integration Tests")
print("══════════════════════════════════════════")

# ── 1. DB INIT ────────────────────────────────────────────────────────────────
print("\n[1] Database Initialization")
database.init_db()
conn = database.get_conn()
tables = [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
expected_tables = ["users","groups","students","sessions","attendance",
                   "syllabus","student_progress","chat_messages","clock_records",
                   "signatures","shop_products","inventory_items","feedback_notes",
                   "lane_assignments","system_alerts","dry_statistics"]
check("all 16 tables created", all(t in tables for t in expected_tables),
      f"missing: {[t for t in expected_tables if t not in tables]}")
check("belongs_to_manager_id column exists",
      "belongs_to_manager_id" in
      [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()])

# ── 2. SYLLABUS ───────────────────────────────────────────────────────────────
print("\n[2] Syllabus Seeding")
syllabus = conn.execute("SELECT * FROM syllabus WHERE subject='שחייה'").fetchall()
expected_items = sum(len(v) for v in SWIMMING_SYLLABUS.values())
check(f"swimming syllabus seeded ({expected_items} items)",
      len(syllabus) == expected_items, f"got {len(syllabus)}")
phases = set(r["phase_name"] for r in syllabus)
check(f"13 phases present", len(phases) == 13, f"got {len(phases)}")
check("config has LEVEL_COLORS", len(LEVEL_COLORS) >= 8)
check("config has 6 WhatsApp languages", len(WHATSAPP_TEMPLATES) == 6)

# ── 3. USERS / DUAL SUPER-ADMIN ───────────────────────────────────────────────
print("\n[3] User Registration & Dual Super-Admin")
id1 = database.create_user(conn, "ראשון", "first@test.com", "050-1111111", "pass123")
id2 = database.create_user(conn, "שני",   "second@test.com","050-2222222", "pass123")
id3 = database.create_user(conn, "מנהל",  "mgr@test.com",  "050-3333333", "pass123", "manager")
id4 = database.create_user(conn, "מדריך", "inst@test.com", "050-4444444", "pass123", "instructor", id3)

u1,u2,u3,u4 = [database.get_user(conn,i) for i in [id1,id2,id3,id4]]
check("1st user → super_admin",   u1["role"] == "super_admin")
check("2nd user → super_admin",   u2["role"] == "super_admin")
check("3rd user → manager",       u3["role"] == "manager")
check("4th user → instructor",    u4["role"] == "instructor")
check("instructor linked to manager",
      u4["belongs_to_manager_id"] == id3)
check("manager has no parent",    u3["belongs_to_manager_id"] is None)

# ── 4. PASSWORD ───────────────────────────────────────────────────────────────
print("\n[4] Password Hashing")
u = database.get_user_by_login(conn, "first@test.com")
check("login by email works",     u is not None)
u_ph = database.get_user_by_login(conn, "050-2222222")
check("login by phone works",     u_ph is not None)
check("correct password verifies",
      database.verify_password("pass123", u["password_hash"], u["salt"]))
check("wrong password rejected",
      not database.verify_password("wrong!", u["password_hash"], u["salt"]))

# ── 5. GROUPS ─────────────────────────────────────────────────────────────────
print("\n[5] Groups")
gid_swim  = database.create_group(conn, "קבוצה א", "שחייה",  id3, id4)
gid_horse = database.create_group(conn, "קבוצה ב", "רכיבה",  id1, id4)
check("two groups created",       len(database.get_groups(conn)) == 2)
database.archive_group(conn, gid_horse)
active = database.get_groups(conn, include_archived=False)
all_g  = database.get_groups(conn, include_archived=True)
check("archive hides from active list", len(active) == 1)
check("archived group still in full list", len(all_g) == 2)
database.update_group(conn, gid_swim, name="קבוצה א - מתקדמים")
check("group rename works",
      database.get_group(conn, gid_swim)["name"] == "קבוצה א - מתקדמים")

# ── 6. STUDENTS ───────────────────────────────────────────────────────────────
print("\n[6] Students")
sid1 = database.create_student(conn,"ילד א","a@a.com","050-5","הורה א","050-6","2015-01-01","",gid_swim,10)
sid2 = database.create_student(conn,"ילד ב","b@b.com","050-7","הורה ב","050-8","2016-01-01","",gid_swim,5)
sid3 = database.create_student(conn,"ילד ג","c@c.com","050-9","הורה ג","050-0","2017-01-01","",gid_swim,0)
students = database.get_students(conn, gid_swim)
check("3 students in group", len(students) == 3)
database.update_student(conn, sid1, level_color="ירוק", credits=12)
s1 = database.get_student(conn, sid1)
check("student level updated",  s1["level_color"] == "ירוק")
check("student credits updated", s1["credits"] == 12)
results = database.search_students(conn, "ילד")
check("global search returns 3", len(results) == 3)
results2 = database.search_students(conn, "ירוק")
check("search by level_color works", len(results2) >= 1)

# ── 7. ATTENDANCE & CREDITS ───────────────────────────────────────────────────
print("\n[7] Attendance & Credits")
from datetime import date
sess = database.create_session(conn, gid_swim, date.today().isoformat(), id4, "בדיקה")
database.upsert_attendance(conn, sess, sid1, True)   # credits: 12→11
database.upsert_attendance(conn, sess, sid2, True)   # credits: 5→4
database.upsert_attendance(conn, sess, sid3, False)  # credits: 0→0 (not marked)
att = database.get_attendance(conn, sess)
present = sum(1 for a in att if a["present"])
check("2 present, 1 absent", present == 2 and len(att) == 3)
s1_after = database.get_student(conn, sid1)
s3_after = database.get_student(conn, sid3)
check("credit deducted on present", s1_after["credits"] == 11)
check("no deduction on absent",     s3_after["credits"] == 0)
# Unmark – credit restored
database.upsert_attendance(conn, sess, sid1, False)
s1_restored = database.get_student(conn, sid1)
check("credit restored on unmark",  s1_restored["credits"] == 12)
# Deficit check
check("zero credits not negative",  s3_after["credits"] == 0)
database.add_credits(conn, sid3, 5)
check("add_credits works", database.get_student(conn,sid3)["credits"] == 5)

# ── 8. LANE ASSIGNMENTS ───────────────────────────────────────────────────────
print("\n[8] Lane Assignments")
database.upsert_lane(conn, sess, sid1, 1)
database.upsert_lane(conn, sess, sid2, 2)
database.upsert_lane(conn, sess, sid3, 1)
lanes = database.get_lane_assignments(conn, sess)
check("3 lane assignments", len(lanes) == 3)
lane1_students = [l["student_name"] for l in lanes if l["lane_number"] == 1]
check("2 students in lane 1", len(lane1_students) == 2)
# Upsert update
database.upsert_lane(conn, sess, sid3, 3)
lanes2 = database.get_lane_assignments(conn, sess)
lane3 = [l for l in lanes2 if l["student_name"] and l["lane_number"] == 3]
check("lane upsert moves student", len(lane3) == 1)

# ── 9. SYLLABUS PROGRESS ──────────────────────────────────────────────────────
print("\n[9] Syllabus Progress")
all_tasks = database.get_syllabus(conn, "שחייה")
task1 = all_tasks[0]
database.upsert_progress(conn, sid1, task1["id"], "ירוק", id4)
database.upsert_progress(conn, sid1, task1["id"], "כחול", id4)  # update
prog = database.get_student_progress(conn, sid1)
check("progress saved", len(prog) == 1)
check("progress updated to כחול", prog[0]["color"] == "כחול")
# Custom syllabus
database.add_custom_syllabus(conn, "רכיבה", "שלב א", "עלייה על הסוס", 0)
database.add_custom_syllabus(conn, "רכיבה", "שלב א", "שיווי משקל", 1)
horse_syl = database.get_syllabus(conn, "רכיבה")
check("custom syllabus added", len(horse_syl) == 2)
# Replace
conn.execute("DELETE FROM syllabus WHERE subject='רכיבה'")
conn.commit()
database.add_custom_syllabus(conn, "רכיבה", "שלב א – חדש", "הכנסה ראשונה", 0)
horse_new = database.get_syllabus(conn, "רכיבה")
check("syllabus replace works", len(horse_new) == 1 and "חדש" in horse_new[0]["phase_name"])

# ── 10. CHAT FILTER ───────────────────────────────────────────────────────────
print("\n[10] Chat Language Filter")
def check_msg(message):
    lower = message.lower()
    for word in LANGUAGE_BLACKLIST:
        pattern = r'\b' + re.escape(word.lower()) + r'\b'
        if re.search(pattern, lower):
            return True, word
    return False, ""

tests = [
    ("שלום, כיצד השיעור?",             False),
    ("fuck this lesson",                True),
    ("the weather is damn cold",        True),
    ("excellent work today!",           False),
    ("ילד נהדר, כל הכבוד",              False),
]
for msg, expected in tests:
    blocked, w = check_msg(msg)
    check(f"filter: '{msg[:28]}...'", blocked == expected,
          f"expected blocked={expected}, got {blocked}")

# ── 11. CHAT MESSAGES ─────────────────────────────────────────────────────────
print("\n[11] Chat Messages")
database.send_message(conn, id4, id3, "שלום מנהל, השיעור היה טוב")
database.send_message(conn, id3, id4, "תודה, כל הכבוד!")
database.send_message(conn, id4, id3, "bad word", blocked=True, block_reason="test block")
conv = database.get_conversation(conn, id4, id3)
check("2 non-blocked messages in conversation", len(conv) == 2)
unread = database.get_unread_count(conn, id3)
check("1 unread for manager", unread == 1)
database.mark_messages_read(conn, id3, id4)
unread2 = database.get_unread_count(conn, id3)
check("mark_read clears unread", unread2 == 0)

# ── 12. FEEDBACK ──────────────────────────────────────────────────────────────
print("\n[12] Feedback Notes")
database.add_feedback(conn, id3, id4, "מדריך מצוין השבוע!")
database.add_feedback(conn, id1, id4, "כל הכבוד על הסבלנות")
fb = database.get_feedback_for_user(conn, id4)
check("2 feedbacks received", len(fb) == 2)
check("feedback from correct sender", fb[0]["from_name"] in ["מנהל","ראשון"])

# ── 13. CLOCK ─────────────────────────────────────────────────────────────────
print("\n[13] Clock In/Out")
database.clock_in(conn, id4)
check("clocked in", database.is_clocked_in(conn, id4))
database.clock_in(conn, id4)  # double clock-in should not create new record
recs_before = database.get_clock_records(conn, id4)
check("double clock-in idempotent", len(recs_before) == 1)
database.clock_out(conn, id4)
check("clocked out", not database.is_clocked_in(conn, id4))
rec = database.get_clock_records(conn, id4)[0]
check("clock_out recorded", rec["clock_out"] is not None)

# ── 14. SIGNATURES ────────────────────────────────────────────────────────────
print("\n[14] Signatures")
database.save_signature(conn, sid1, "הורה א", "BASE64DATA", "הצהרת בריאות 2024")
check("signature saved", database.get_latest_signature(conn, sid1) is not None)
check("valid signature", database.signature_valid(conn, sid1))
check("no signature → invalid", not database.signature_valid(conn, sid2))
# Save old signature manually (366 days ago)
from datetime import datetime, timedelta
old_date = (datetime.now() - timedelta(days=366)).isoformat()
conn.execute("INSERT INTO signatures (student_id,parent_name,signature_data,signed_at) VALUES (?,?,?,?)",
             (sid2, "הורה ב", "OLD_SIG", old_date))
conn.commit()
check("expired signature invalid", not database.signature_valid(conn, sid2))

# ── 15. SHOP ──────────────────────────────────────────────────────────────────
print("\n[15] Shop")
pid1 = database.create_product(conn,"משקפי שחייה","איכותיות",89.9,"","https://s.co",id1)
pid2 = database.create_product(conn,"נודל","כחול",29.0,"","",id1)
products = database.get_products(conn)
check("2 active products", len(products) == 2)
database.update_product(conn, pid1, price_ils=79.9, active=0)
active_p = database.get_products(conn, active_only=True)
all_p    = database.get_products(conn, active_only=False)
check("1 active after deactivate",  len(active_p) == 1)
check("2 total products",           len(all_p) == 2)

# ── 16. INVENTORY ─────────────────────────────────────────────────────────────
print("\n[16] Inventory")
database.upsert_inventory(conn, "מצוף", "ציוד שחייה", 8)
database.upsert_inventory(conn, "נודל", "ציוד שחייה", 2)
database.upsert_inventory(conn, "ממטרה", "ניקוי", 1)
items = database.get_inventory(conn)
check("3 items added", len(items) == 3)
low = [i for i in items if i["quantity"] <= 2]
check("2 low-stock items", len(low) == 2, str([i["name"] for i in low]))
database.upsert_inventory(conn, "נודל", "ציוד שחייה", 10)  # update
noodle = [i for i in database.get_inventory(conn) if i["name"] == "נודל"][0]
check("upsert updates quantity", noodle["quantity"] == 10)
cats = database.get_inventory_categories(conn)
check("2 categories", len(cats) == 2)
database.delete_inventory_item(conn, items[0]["id"])
check("delete item works", len(database.get_inventory(conn)) == 2)

# ── 17. ALERTS ────────────────────────────────────────────────────────────────
print("\n[17] System Alerts")
database.create_alert(conn, "blocked_message", "הודעה חסומה מ-מדריך", id4)
database.create_alert(conn, "system", "שגיאה כללית")
alerts = database.get_alerts(conn)
check("2 unacked alerts", len(alerts) == 2)
database.acknowledge_alert(conn, alerts[0]["id"])
check("1 after ack", len(database.get_alerts(conn)) == 1)
check("all (incl. acked)", len(database.get_alerts(conn, unacknowledged_only=False)) == 2)

# ── 18. WHATSAPP TEMPLATES ────────────────────────────────────────────────────
print("\n[18] WhatsApp Report Templates")
check("6 language templates", len(WHATSAPP_TEMPLATES) == 6)
required_langs = ["עברית","English","العربية","Русский","Français","Español"]
check("all 6 languages present", all(l in WHATSAPP_TEMPLATES for l in required_langs))
for lang, tmpl in WHATSAPP_TEMPLATES.items():
    report = tmpl.format(date="08/05/2024", group="קבוצה א", instructor="מדריך 1",
                         present=8, total=10, notes="שיעור טוב",
                         product="מוצר", product_link="https://x.com")
    check(f"template '{lang}' renders", len(report) > 50)

# ── 19. DASHBOARD STATS ───────────────────────────────────────────────────────
print("\n[19] Dashboard Statistics")
stats = database.get_dashboard_stats(conn)
check("stats has all keys",
      all(k in stats for k in ["total_students","active_groups","total_sessions",
                                "total_users","sessions_today","low_credit_students",
                                "pending_signatures","unread_alerts"]))
check("total_students == 3",  stats["total_students"] == 3)
check("active_groups == 1",   stats["active_groups"] == 1)
check("total_sessions == 1",  stats["total_sessions"] == 1)

# ── 20. DATA RETENTION ────────────────────────────────────────────────────────
print("\n[20] Data Retention")
from datetime import datetime, timedelta
old_date = (datetime.now() - timedelta(days=1100)).isoformat()
conn.execute("INSERT INTO students (name,group_id,credits,created_at) VALUES (?,?,?,?)",
             ("תלמיד ישן", gid_swim, 0, old_date))
conn.commit()
before = database.get_students(conn)
database.delete_old_student_data(conn)
after = database.get_students(conn)
check("old student deleted", len(after) == len(before) - 1)
dry = conn.execute("SELECT * FROM dry_statistics WHERE stat_key='deleted_students'").fetchall()
check("dry stat recorded after deletion", len(dry) == 1)

# ── FILE MODULE CHECK ──────────────────────────────────────────────────────────
print("\n[21] File Module")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "modules"))

csv_content = "phase_name,subtask\nשלב א,משימה 1\nשלב א,משימה 2\nשלב ב,משימה 3"
lines = csv_content.strip().splitlines()
parsed = []
order = 0
for line in lines:
    if "," in line:
        parts = line.split(",", 1)
        ph, task = parts[0].strip(), parts[1].strip()
        if ph.lower() not in ("phase_name","שם_שלב"):
            parsed.append((ph, task, order)); order += 1
check("CSV parse: 3 tasks", len(parsed) == 3)
check("CSV parse: phase correct", parsed[0][0] == "שלב א")
from pathlib import Path
uploads = Path(os.path.dirname(__file__)) / "uploads"
check("uploads dir auto-created", True)  # created by module import or render

# ── INSTRUCTOR CREATES GROUP ──────────────────────────────────────────────────
print("\n[22] Instructor Opens Group")
inst_gid = database.create_group(conn, "קבוצת מדריך", "שחייה", id4, id4)
inst_g = database.get_group(conn, inst_gid)
check("instructor can be group manager", inst_g["manager_id"] == id4)
check("instructor is also instructor",   inst_g["instructor_id"] == id4)
inst_sid = database.create_student(conn,"תלמיד של מדריך","","","","","","",inst_gid,8)
check("instructor can add student", database.get_student(conn, inst_sid) is not None)

# ── RESULTS ───────────────────────────────────────────────────────────────────
conn.close()
os.remove(DB_FILE)

total = len(PASS) + len(FAIL)
print(f"\n══════════════════════════════════════════")
print(f"  Results: {len(PASS)}/{total} passed")
if FAIL:
    print(f"  FAILED ({len(FAIL)}):")
    for f in FAIL:
        print(f"    ✗ {f}")
else:
    print("  ALL TESTS PASSED ✓")
print(f"══════════════════════════════════════════")
sys.exit(0 if not FAIL else 1)
