"""
web_app.py
Web-based GUI for Student Academic & Activity Ledger.
Provides a browser-accessible, responsive interface for college submissions and remote evaluations.
Preserves 100% of the desktop application's core logic:
- TE Regular Eligibility evaluation (eligibility.py)
- Formula-safe 6-table CSV exports (csv_export.py)
- Google Sheets one-way synchronization & error diagnosis (google_sheets_sync.py)
- Fictional demo student records (demo_data_proposal.py)

Dual-mode Database Support:
- Primary: Connects to local or remote MySQL (student_academic_ledger).
- Fallback: Automatically falls back to an embedded SQLite database pre-seeded
  with demo records if MySQL is offline or during cloud deployment.
"""

import os
import io
import zipfile
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from flask import Flask, render_template, request, jsonify, send_file

# Import existing domain logic
from eligibility import StudentEligibilityChecker
from csv_export import LedgerCSVExporter
from google_sheets_sync import GoogleSheetsSyncService
from demo_data_proposal import DEMO_STUDENTS

app = Flask(__name__)
app.config["SECRET_KEY"] = "student-ledger-web-secret-key-2026"

DB_NAME = "student_academic_ledger"
SQLITE_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "student_ledger_web.db")


class LedgerDBManager:
    """
    Manages database access with seamless MySQL support and automatic SQLite fallback.
    Ensures the web app works flawlessly both on a local machine with MySQL and
    when deployed to cloud platforms (Render, PythonAnywhere, etc.) where local MySQL
    is not running.
    """

    def __init__(self):
        self.mode = "unknown"
        self.mysql_config = {
            "host": os.environ.get("MYSQL_HOST", "localhost"),
            "port": int(os.environ.get("MYSQL_PORT", 3306)),
            "user": os.environ.get("MYSQL_USER", "root"),
            "password": os.environ.get("MYSQL_PWD", os.environ.get("MYSQL_PASSWORD", "")),
            "database": DB_NAME
        }
        self.init_database()

    def get_mysql_connection(self):
        try:
            import mysql.connector
            conn = mysql.connector.connect(**self.mysql_config)
            return conn
        except Exception:
            return None

    def get_sqlite_connection(self):
        conn = sqlite3.connect(SQLITE_DB)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        # 1. Try MySQL
        conn = self.get_mysql_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SHOW TABLES")
                tables = [r[0] for r in cursor.fetchall()]
                cursor.close()
                conn.close()
                if "students" in tables:
                    self.mode = "mysql"
                    return
            except Exception:
                pass

        # 2. Fallback to SQLite (ensures hosted demo works without MySQL server setup)
        self.mode = "sqlite"
        self._init_sqlite_schema()

    def _init_sqlite_schema(self):
        conn = self.get_sqlite_connection()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id INTEGER PRIMARY KEY AUTOINCREMENT,
                roll_number TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                date_of_birth TEXT,
                email TEXT,
                admission_year INTEGER,
                tenth_percentage REAL,
                twelfth_percentage REAL,
                current_status TEXT DEFAULT 'Active',
                year_of_study TEXT DEFAULT 'TE',
                student_type TEXT DEFAULT 'Regular',
                is_on_attendance_roll INTEGER DEFAULT 1,
                submission_status TEXT DEFAULT 'Draft'
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS semesters (
                semester_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                semester_number INTEGER NOT NULL,
                sgpa REAL,
                cgpa REAL,
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                UNIQUE (student_id, semester_number)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                subject_id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_name TEXT NOT NULL,
                subject_code TEXT,
                subject_type TEXT DEFAULT 'Theory'
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS subject_results (
                result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                semester_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                internal_marks REAL,
                external_marks REAL,
                lab_marks REAL,
                total_marks REAL,
                result_status TEXT DEFAULT 'Pass',
                FOREIGN KEY (semester_id) REFERENCES semesters(semester_id),
                FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS seminars (
                seminar_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                seminar_name TEXT NOT NULL,
                seminar_type TEXT DEFAULT 'Internal',
                event_date TEXT,
                certificate_reference TEXT,
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                activity_name TEXT NOT NULL,
                category TEXT DEFAULT 'Technical',
                activity_date TEXT,
                description TEXT,
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS drop_years (
                drop_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                start_year INTEGER,
                end_year INTEGER,
                reason TEXT,
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        """)

        # If empty, populate DEMO_STUDENTS
        cur.execute("SELECT COUNT(*) FROM students")
        count = cur.fetchone()[0]
        if count == 0:
            self._seed_sqlite_demo(conn)

        conn.commit()
        conn.close()

    def _seed_sqlite_demo(self, conn):
        cur = conn.cursor()
        for s in DEMO_STUDENTS:
            cur.execute("""
                INSERT OR IGNORE INTO students (
                    roll_number, full_name, date_of_birth, email,
                    admission_year, tenth_percentage, twelfth_percentage,
                    current_status, year_of_study, student_type,
                    is_on_attendance_roll, submission_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                s["roll_number"], s["full_name"], s.get("date_of_birth"), s.get("email"),
                s.get("admission_year"), s.get("tenth_percentage"), s.get("twelfth_percentage"),
                s.get("current_status", "Active"), s.get("year_of_study", "TE"),
                s.get("student_type", "Regular"), s.get("is_on_attendance_roll", 1), "Draft"
            ))
            student_id = cur.lastrowid
            if not student_id:
                cur.execute("SELECT student_id FROM students WHERE roll_number = ?", (s["roll_number"],))
                student_id = cur.fetchone()[0]

            # Semesters & Marks
            for sem in s.get("semesters", []):
                cur.execute("""
                    INSERT OR REPLACE INTO semesters (student_id, semester_number, sgpa, cgpa)
                    VALUES (?, ?, ?, ?)
                """, (student_id, sem["semester_number"], sem.get("sgpa"), sem.get("cgpa")))
                semester_id = cur.lastrowid

            for m in s.get("marks", []):
                cur.execute("SELECT subject_id FROM subjects WHERE subject_name = ?", (m["subject_name"],))
                sub_row = cur.fetchone()
                if sub_row:
                    subject_id = sub_row[0]
                else:
                    cur.execute("INSERT INTO subjects (subject_name, subject_type) VALUES (?, ?)",
                                (m["subject_name"], m.get("subject_type", "Theory")))
                    subject_id = cur.lastrowid

                # find semester_id
                cur.execute("SELECT semester_id FROM semesters WHERE student_id = ? AND semester_number = ?",
                            (student_id, m["semester_number"]))
                sem_row = cur.fetchone()
                if sem_row:
                    sem_id = sem_row[0]
                    cur.execute("""
                        INSERT INTO subject_results (semester_id, subject_id, internal_marks, external_marks, lab_marks)
                        VALUES (?, ?, ?, ?, ?)
                    """, (sem_id, subject_id, m.get("internal_marks"), m.get("external_marks"), m.get("lab_marks")))

            for sm in s.get("seminars", []):
                cur.execute("""
                    INSERT INTO seminars (student_id, seminar_name, seminar_type, event_date, certificate_reference)
                    VALUES (?, ?, ?, ?, ?)
                """, (student_id, sm["seminar_name"], sm.get("seminar_type", "Internal"),
                      sm.get("event_date"), sm.get("certificate_reference")))

            for a in s.get("activities", []):
                cur.execute("""
                    INSERT INTO activities (student_id, activity_name, category, activity_date, description)
                    VALUES (?, ?, ?, ?, ?)
                """, (student_id, a["activity_name"], a.get("category", "Technical"),
                      a.get("activity_date"), a.get("description")))

            for d in s.get("drop_years", []):
                cur.execute("""
                    INSERT INTO drop_years (student_id, start_year, end_year, reason)
                    VALUES (?, ?, ?, ?)
                """, (student_id, d["start_year"], d["end_year"], d.get("reason")))

    def fetch_students(self, search: str = "") -> List[Dict[str, Any]]:
        search = search.strip()
        if self.mode == "mysql":
            conn = self.get_mysql_connection()
            if not conn:
                self.mode = "sqlite"
                return self.fetch_students(search)
            cur = conn.cursor(dictionary=True)
            if search:
                query = "SELECT * FROM students WHERE full_name LIKE %s OR roll_number LIKE %s ORDER BY full_name"
                cur.execute(query, (f"%{search}%", f"%{search}%"))
            else:
                cur.execute("SELECT * FROM students ORDER BY full_name")
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return rows
        else:
            conn = self.get_sqlite_connection()
            cur = conn.cursor()
            if search:
                query = "SELECT * FROM students WHERE full_name LIKE ? OR roll_number LIKE ? ORDER BY full_name"
                cur.execute(query, (f"%{search}%", f"%{search}%"))
            else:
                cur.execute("SELECT * FROM students ORDER BY full_name")
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows

    def fetch_student_detail(self, student_id: int) -> Optional[Dict[str, Any]]:
        if self.mode == "mysql":
            conn = self.get_mysql_connection()
            if not conn:
                self.mode = "sqlite"
                return self.fetch_student_detail(student_id)
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM students WHERE student_id = %s", (student_id,))
            student = cur.fetchone()
            if not student:
                cur.close()
                conn.close()
                return None

            cur.execute("SELECT * FROM semesters WHERE student_id = %s ORDER BY semester_number", (student_id,))
            semesters = cur.fetchall()

            cur.execute("""
                SELECT s.semester_number, sub.subject_name, sub.subject_type,
                       r.internal_marks, r.external_marks, r.lab_marks, r.total_marks, r.result_status
                FROM subject_results r
                JOIN semesters s ON r.semester_id=s.semester_id
                JOIN subjects sub ON r.subject_id=sub.subject_id
                WHERE s.student_id = %s
                ORDER BY s.semester_number, sub.subject_name
            """, (student_id,))
            marks = cur.fetchall()

            cur.execute("SELECT * FROM seminars WHERE student_id = %s ORDER BY event_date DESC", (student_id,))
            seminars = cur.fetchall()

            cur.execute("SELECT * FROM activities WHERE student_id = %s ORDER BY activity_date DESC", (student_id,))
            activities = cur.fetchall()

            cur.execute("SELECT * FROM drop_years WHERE student_id = %s ORDER BY start_year", (student_id,))
            drop_years = cur.fetchall()

            cur.close()
            conn.close()
        else:
            conn = self.get_sqlite_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
            row = cur.fetchone()
            if not row:
                conn.close()
                return None
            student = dict(row)

            cur.execute("SELECT * FROM semesters WHERE student_id = ? ORDER BY semester_number", (student_id,))
            semesters = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                SELECT s.semester_number, sub.subject_name, sub.subject_type,
                       r.internal_marks, r.external_marks, r.lab_marks, r.total_marks, r.result_status
                FROM subject_results r
                JOIN semesters s ON r.semester_id=s.semester_id
                JOIN subjects sub ON r.subject_id=sub.subject_id
                WHERE s.student_id = ?
                ORDER BY s.semester_number, sub.subject_name
            """, (student_id,))
            marks = [dict(r) for r in cur.fetchall()]

            cur.execute("SELECT * FROM seminars WHERE student_id = ? ORDER BY event_date DESC", (student_id,))
            seminars = [dict(r) for r in cur.fetchall()]

            cur.execute("SELECT * FROM activities WHERE student_id = ? ORDER BY activity_date DESC", (student_id,))
            activities = [dict(r) for r in cur.fetchall()]

            cur.execute("SELECT * FROM drop_years WHERE student_id = ? ORDER BY start_year", (student_id,))
            drop_years = [dict(r) for r in cur.fetchall()]
            conn.close()

        # Check TE Regular Eligibility using domain module
        is_eligible, elig_msg, elig_details = StudentEligibilityChecker.check_te_regular_eligibility(student)

        return {
            "student": student,
            "eligibility": {
                "is_eligible": is_eligible,
                "message": elig_msg,
                "details": elig_details
            },
            "semesters": semesters,
            "marks": marks,
            "seminars": seminars,
            "activities": activities,
            "drop_years": drop_years
        }

    def fetch_full_ledger_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """Fetches normalized relational tables into a dictionary for CSV Export and Google Sheets sync."""
        if self.mode == "mysql":
            conn = self.get_mysql_connection()
            if not conn:
                self.mode = "sqlite"
                return self.fetch_full_ledger_data()
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM students ORDER BY roll_number")
            students = cur.fetchall()

            cur.execute("""
                SELECT s.*, st.roll_number, st.full_name
                FROM semesters s
                JOIN students st ON s.student_id=st.student_id
                ORDER BY st.roll_number, s.semester_number
            """)
            semesters = cur.fetchall()

            cur.execute("""
                SELECT s.semester_number, sub.subject_name, sub.subject_type,
                       r.internal_marks, r.external_marks, r.lab_marks,
                       st.roll_number, st.full_name
                FROM subject_results r
                JOIN semesters s ON r.semester_id=s.semester_id
                JOIN subjects sub ON r.subject_id=sub.subject_id
                JOIN students st ON s.student_id=st.student_id
                ORDER BY st.roll_number, s.semester_number, sub.subject_name
            """)
            marks = cur.fetchall()

            cur.execute("""
                SELECT sm.*, st.roll_number, st.full_name
                FROM seminars sm
                JOIN students st ON sm.student_id=st.student_id
                ORDER BY st.roll_number, sm.event_date DESC
            """)
            seminars = cur.fetchall()

            cur.execute("""
                SELECT a.*, st.roll_number, st.full_name
                FROM activities a
                JOIN students st ON a.student_id=st.student_id
                ORDER BY st.roll_number, a.activity_date DESC
            """)
            activities = cur.fetchall()

            cur.execute("""
                SELECT d.*, st.roll_number, st.full_name
                FROM drop_years d
                JOIN students st ON d.student_id=st.student_id
                ORDER BY st.roll_number, d.start_year
            """)
            drop_years = cur.fetchall()
            cur.close()
            conn.close()
        else:
            conn = self.get_sqlite_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM students ORDER BY roll_number")
            students = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                SELECT s.*, st.roll_number, st.full_name
                FROM semesters s
                JOIN students st ON s.student_id=st.student_id
                ORDER BY st.roll_number, s.semester_number
            """)
            semesters = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                SELECT s.semester_number, sub.subject_name, sub.subject_type,
                       r.internal_marks, r.external_marks, r.lab_marks,
                       st.roll_number, st.full_name
                FROM subject_results r
                JOIN semesters s ON r.semester_id=s.semester_id
                JOIN subjects sub ON r.subject_id=sub.subject_id
                JOIN students st ON s.student_id=st.student_id
                ORDER BY st.roll_number, s.semester_number, sub.subject_name
            """)
            marks = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                SELECT sm.*, st.roll_number, st.full_name
                FROM seminars sm
                JOIN students st ON sm.student_id=st.student_id
                ORDER BY st.roll_number, sm.event_date DESC
            """)
            seminars = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                SELECT a.*, st.roll_number, st.full_name
                FROM activities a
                JOIN students st ON a.student_id=st.student_id
                ORDER BY st.roll_number, a.activity_date DESC
            """)
            activities = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                SELECT d.*, st.roll_number, st.full_name
                FROM drop_years d
                JOIN students st ON d.student_id=st.student_id
                ORDER BY st.roll_number, d.start_year
            """)
            drop_years = [dict(r) for r in cur.fetchall()]
            conn.close()

        return {
            "students": students,
            "semesters": semesters,
            "marks": marks,
            "seminars": seminars,
            "activities": activities,
            "drop_years": drop_years
        }

    def add_student(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        roll = data.get("roll_number", "").strip()
        name = data.get("full_name", "").strip()
        if not roll or not name:
            return False, "Roll number and Full Name are required."

        if self.mode == "mysql":
            conn = self.get_mysql_connection()
            if not conn:
                return False, "Database connection unavailable."
            cur = conn.cursor()
            try:
                cur.execute("""
                    INSERT INTO students (
                        roll_number, full_name, date_of_birth, email,
                        admission_year, tenth_percentage, twelfth_percentage,
                        current_status, year_of_study, student_type, is_on_attendance_roll
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    roll, name, data.get("date_of_birth") or None, data.get("email") or None,
                    data.get("admission_year") or None, data.get("tenth_percentage") or None,
                    data.get("twelfth_percentage") or None, data.get("current_status", "Active"),
                    data.get("year_of_study", "TE"), data.get("student_type", "Regular"),
                    1 if str(data.get("is_on_attendance_roll")).lower() in ("1", "true", "on roll") else 0
                ))
                conn.commit()
                cur.close()
                conn.close()
                return True, "Student added successfully."
            except Exception as e:
                conn.rollback()
                cur.close()
                conn.close()
                return False, str(e)
        else:
            conn = self.get_sqlite_connection()
            cur = conn.cursor()
            try:
                cur.execute("""
                    INSERT INTO students (
                        roll_number, full_name, date_of_birth, email,
                        admission_year, tenth_percentage, twelfth_percentage,
                        current_status, year_of_study, student_type, is_on_attendance_roll
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    roll, name, data.get("date_of_birth") or None, data.get("email") or None,
                    data.get("admission_year") or None, data.get("tenth_percentage") or None,
                    data.get("twelfth_percentage") or None, data.get("current_status", "Active"),
                    data.get("year_of_study", "TE"), data.get("student_type", "Regular"),
                    1 if str(data.get("is_on_attendance_roll")).lower() in ("1", "true", "on roll") else 0
                ))
                conn.commit()
                conn.close()
                return True, "Student added successfully."
            except Exception as e:
                conn.close()
                return False, str(e)

    def seed_demo_students(self) -> Tuple[bool, str]:
        if self.mode == "sqlite":
            conn = self.get_sqlite_connection()
            self._seed_sqlite_demo(conn)
            conn.commit()
            conn.close()
            return True, f"Successfully seeded {len(DEMO_STUDENTS)} demo students."
        else:
            # MySQL demo seed via execute_demo_seed or direct insertion
            from execute_demo_seed import run_seed
            pwd = self.mysql_config.get("password")
            ok = run_seed(pwd)
            if ok:
                return True, f"Successfully seeded {len(DEMO_STUDENTS)} demo students into MySQL."
            return False, "Failed to execute MySQL demo seed. Please check database permissions."


db = LedgerDBManager()
sheets_service = GoogleSheetsSyncService()


# ---------------- API & PAGE ROUTES ----------------

@app.route("/healthz")
@app.route("/health")
def health():
    return jsonify({"status": "healthy", "database": db.mode}), 200


@app.route("/")
def index():
    return render_template("index.html", db_mode=db.mode)


@app.route("/api/status")
def get_status():
    return jsonify({
        "db_mode": db.mode,
        "database": DB_NAME if db.mode == "mysql" else "SQLite (Cloud / Demo Mode)",
        "sheets_configured": sheets_service.is_configured()[0],
        "sheets_status": sheets_service.is_configured()[1]
    })


@app.route("/api/students")
def api_students():
    search = request.args.get("q", "")
    students = db.fetch_students(search)
    return jsonify(students)


@app.route("/api/student/<int:student_id>")
def api_student_detail(student_id: int):
    detail = db.fetch_student_detail(student_id)
    if not detail:
        return jsonify({"error": "Student not found"}), 404
    return jsonify(detail)


@app.route("/api/student", methods=["POST"])
def api_add_student():
    data = request.json or {}
    ok, msg = db.add_student(data)
    if ok:
        return jsonify({"success": True, "message": msg})
    return jsonify({"success": False, "message": msg}), 400


@app.route("/api/seed_demo", methods=["POST"])
def api_seed_demo():
    ok, msg = db.seed_demo_students()
    if ok:
        return jsonify({"success": True, "message": msg})
    return jsonify({"success": False, "message": msg}), 500


@app.route("/api/sheets/test", methods=["POST"])
def api_sheets_test():
    ok, msg = sheets_service.test_connection()
    return jsonify({"success": ok, "message": msg})


@app.route("/api/sheets/sync", methods=["POST"])
def api_sheets_sync():
    data = db.fetch_full_ledger_data()
    ok, msg = sheets_service.push_to_google_sheets(data)
    return jsonify({"success": ok, "message": msg})


@app.route("/api/sheets/config", methods=["GET", "POST"])
def api_sheets_config():
    if request.method == "POST":
        data = request.json or {}
        sid = data.get("spreadsheet_id", "").strip()
        cpath = data.get("credentials_path", "").strip()
        enabled = bool(data.get("enabled", True))
        sheets_service.save_config(sid, cpath, enabled)
        return jsonify({"success": True, "message": "Configuration saved."})

    cfg = sheets_service.load_config()
    ready, status_msg = sheets_service.is_configured()
    sa_email = sheets_service.get_service_account_email() or "Not detected"
    return jsonify({
        "spreadsheet_id": cfg.get("spreadsheet_id", ""),
        "credentials_path": cfg.get("credentials_path", ""),
        "enabled": cfg.get("enabled", False),
        "ready": ready,
        "status_message": status_msg,
        "service_account_email": sa_email
    })


@app.route("/export/csv_zip")
def export_csv_zip():
    """Generates the 6 validated CSV files in memory and returns them as a zip download."""
    data = db.fetch_full_ledger_data()

    # Create temporary in-memory zip
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        import tempfile
        import shutil
        temp_dir = tempfile.mkdtemp()
        try:
            exporter = LedgerCSVExporter(temp_dir)
            exporter.export_all(data)

            for fname in os.listdir(temp_dir):
                fpath = os.path.join(temp_dir, fname)
                if os.path.isfile(fpath):
                    zip_file.write(fpath, arcname=fname)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    zip_buffer.seek(0)
    filename = f"Student_Ledger_CSVs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 65)
    print("Student Academic & Activity Ledger - Web Interface")
    print(f"Database Mode: {db.mode.upper()}")
    print(f"Running at: http://localhost:{port}")
    print("=" * 65)
    app.run(host="0.0.0.0", port=port, debug=False)
