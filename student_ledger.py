"""
Student Academic & Activity Ledger
A desktop application for managing student academic records, marks, progression,
seminars, activities, and gap years, with validated CSV export and Google Sheets sync.
"""

import os
import re
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import mysql.connector
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from csv_export import LedgerCSVExporter, sanitize_for_spreadsheet
from eligibility import StudentEligibilityChecker
from google_sheets_sync import GoogleSheetsSyncService
from demo_data_proposal import DEMO_STUDENTS

DB_NAME = "student_academic_ledger"


class StudentLedgerApp:
    def __init__(self, root, db_password):
        self.root = root
        self.root.title("Student Academic & Activity Ledger")
        self.root.geometry("1180x760")
        self.root.minsize(950, 650)
        self.db_password = db_password

        try:
            self.conn = mysql.connector.connect(
                host="localhost",
                port=3306,
                user="root",
                password=db_password,
                database=DB_NAME
            )
        except mysql.connector.Error as err:
            messagebox.showerror(
                "Database Connection Error",
                f"MySQL connection failed:\n{err}\n\n"
                "Check that MySQL Server is running and the password is correct."
            )
            root.destroy()
            return

        self.student_id = None
        self.student_name = ""
        self.student_roll = ""
        self.student_data = {}
        self.available_student_columns = self.detect_student_columns()

        self.sheets_service = GoogleSheetsSyncService()
        self.build_ui()
        self.auto_seed_if_needed()
        self.run_db_audit()
        self.load_students()

    def auto_seed_if_needed(self):
        """Checks if demo students exist; if not, executes the approved seed_fictional_demo_plan.sql using self.conn."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM students WHERE roll_number = 'DEMO-TE-001'")
            cnt = cursor.fetchone()[0]
            if cnt == 0 and os.path.exists("seed_fictional_demo_plan.sql"):
                with open("seed_fictional_demo_plan.sql", "r", encoding="utf-8") as f:
                    sql_content = f.read()

                statements = []
                current_stmt = []
                for line in sql_content.splitlines():
                    trimmed = line.strip()
                    if not trimmed or trimmed.startswith("--"):
                        continue
                    current_stmt.append(line)
                    if trimmed.endswith(";"):
                        stmt = "\n".join(current_stmt).strip()
                        if stmt.endswith(";"):
                            stmt = stmt[:-1].strip()
                        if stmt and not stmt.upper().startswith("USE "):
                            statements.append(stmt)
                        current_stmt = []

                for s in statements:
                    cursor.execute(s)
                self.conn.commit()
                print("Auto-seed completed: DEMO-TE-001 and DEMO-TE-002 inserted.")
            cursor.close()
        except Exception as ex:
            self.conn.rollback()
            print(f"Auto-seed note: {ex}")

    def run_db_audit(self):
        """Audits database schema, tables, row counts, and student records without making changes."""
        try:
            import json
            audit = {"database": DB_NAME, "tables": {}, "row_counts": {}, "students_data": []}
            cursor = self.conn.cursor()
            cursor.execute("SHOW TABLES")
            tables = [r[0] for r in cursor.fetchall()]

            for tbl in tables:
                cursor.execute(f"DESCRIBE `{tbl}`")
                cols = [r[0] for r in cursor.fetchall()]
                cursor.execute(f"SELECT COUNT(*) FROM `{tbl}`")
                cnt = cursor.fetchone()[0]
                audit["tables"][tbl] = cols
                audit["row_counts"][tbl] = cnt

            cursor.execute("SELECT student_id, roll_number, full_name FROM students ORDER BY student_id")
            students = cursor.fetchall()
            for sid, roll, name in students:
                s_info = {
                    "student_id": sid,
                    "roll_number": roll,
                    "full_name": name,
                    "semesters": 0,
                    "marks": 0,
                    "seminars": 0,
                    "activities": 0,
                    "drop_years": 0
                }
                if "semesters" in tables:
                    cursor.execute("SELECT COUNT(*) FROM semesters WHERE student_id=%s", (sid,))
                    s_info["semesters"] = cursor.fetchone()[0]
                if "subject_results" in tables and "semesters" in tables:
                    cursor.execute(
                        """SELECT COUNT(*) FROM subject_results r
                           JOIN semesters s ON r.semester_id=s.semester_id
                           WHERE s.student_id=%s""",
                        (sid,)
                    )
                    s_info["marks"] = cursor.fetchone()[0]
                if "seminars" in tables:
                    cursor.execute("SELECT COUNT(*) FROM seminars WHERE student_id=%s", (sid,))
                    s_info["seminars"] = cursor.fetchone()[0]
                if "activities" in tables:
                    cursor.execute("SELECT COUNT(*) FROM activities WHERE student_id=%s", (sid,))
                    s_info["activities"] = cursor.fetchone()[0]
                if "drop_years" in tables:
                    cursor.execute("SELECT COUNT(*) FROM drop_years WHERE student_id=%s", (sid,))
                    s_info["drop_years"] = cursor.fetchone()[0]
                audit["students_data"].append(s_info)

            cursor.close()
            with open("db_schema_audit.json", "w", encoding="utf-8") as f:
                json.dump(audit, f, indent=4)
            self.last_audit = audit
        except Exception as e:
            print(f"Audit notice: {e}")
            self.last_audit = None

    def show_db_audit_dialog(self):
        self.run_db_audit()
        if not hasattr(self, "last_audit") or not self.last_audit:
            messagebox.showinfo("DB Audit", "No database audit information available.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Database Schema & Records Audit")
        dialog.geometry("540x480")
        dialog.transient(self.root)

        txt = tk.Text(dialog, wrap="word", font=("Consolas", 10), padx=10, pady=10)
        txt.pack(fill="both", expand=True)

        lines = ["=" * 55, f"DATABASE AUDIT REPORT: {DB_NAME}", "=" * 55, "", "TABLE ROW COUNTS:"]
        for tbl, cnt in self.last_audit["row_counts"].items():
            lines.append(f"• {tbl:<20} : {cnt} record(s)")

        lines.extend(["", "-" * 55, "STUDENTS & LINKED DATA COUNTS:", "-" * 55])
        for s in self.last_audit["students_data"]:
            lines.append(f"\nStudent: {s['full_name']} (Roll: {s['roll_number']}, ID: {s['student_id']})")
            lines.append(f"  • Semesters      : {s['semesters']}")
            lines.append(f"  • Subject Marks  : {s['marks']}")
            lines.append(f"  • Seminars       : {s['seminars']}")
            lines.append(f"  • Activities     : {s['activities']}")
            lines.append(f"  • Gap/Drop Years : {s['drop_years']}")

        txt.insert("1.0", "\n".join(lines))
        txt.configure(state="disabled")

    def detect_student_columns(self):
        """Detects existing columns in the students table for backward compatibility."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
                   WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'students'""",
                (DB_NAME,)
            )
            cols = {row[0].lower() for row in cursor.fetchall()}
            cursor.close()
            return cols
        except Exception:
            return {"student_id", "roll_number", "full_name", "date_of_birth",
                    "email", "admission_year", "tenth_percentage", "twelfth_percentage", "current_status"}

    def query(self, sql, params=()):
        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def execute_dml(self, sql, params=()):
        """Executes INSERT/UPDATE/DELETE with commit and rollback protection."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(sql, params)
            self.conn.commit()
            last_id = cursor.lastrowid
            cursor.close()
            return (True, last_id)
        except mysql.connector.Error as err:
            self.conn.rollback()
            cursor.close()
            return (False, str(err))

    def build_ui(self):
        # 1. Header Frame
        header = tk.Frame(self.root, bg="#17365D", pady=12)
        header.pack(fill="x")
        tk.Label(
            header,
            text="STUDENT ACADEMIC & ACTIVITY LEDGER",
            font=("Arial", 18, "bold"),
            bg="#17365D", fg="white"
        ).pack()
        tk.Label(
            header,
            text="Academic Records | 3NF Relational Ledger | TE Regular Roll Verification",
            font=("Arial", 10),
            bg="#17365D", fg="#DCE6F1"
        ).pack(pady=(2, 0))

        # 2. Search & Toolbar Frame
        toolbar = ttk.Frame(self.root, padding=8)
        toolbar.pack(fill="x")

        ttk.Label(toolbar, text="Search (Name / Roll):").pack(side="left")
        self.search_entry = ttk.Entry(toolbar, width=28)
        self.search_entry.pack(side="left", padx=6)
        self.search_entry.bind("<Return>", lambda e: self.load_students())

        ttk.Button(toolbar, text="Search", command=self.load_students).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Show All", command=self.show_all_students).pack(side="left", padx=2)
        ttk.Button(toolbar, text="+ Add Student", command=self.add_student).pack(side="left", padx=8)

        # Right-side action buttons
        ttk.Button(toolbar, text="📥 Export CSV", command=self.export_csv_dialog).pack(side="right", padx=4)
        ttk.Button(toolbar, text="🔄 Google Sheets Sync", command=self.google_sheets_dialog).pack(side="right", padx=4)
        ttk.Button(toolbar, text="🧪 Demo Students", command=self.seed_demo_data_dialog).pack(side="right", padx=4)
        ttk.Button(toolbar, text="📊 DB Audit", command=self.show_db_audit_dialog).pack(side="right", padx=4)

        # 3. Main Paned Window
        main = ttk.Panedwindow(self.root, orient="horizontal")
        main.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        left = ttk.Frame(main, padding=5)
        right = ttk.Frame(main, padding=5)
        main.add(left, weight=1)
        main.add(right, weight=3)

        # Left: Student Records List
        ttk.Label(left, text="Student Directory", font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 5))
        self.student_tree = ttk.Treeview(
            left, columns=("roll", "name", "status"),
            show="headings", height=20
        )
        for col, title, width in [
            ("roll", "Roll No", 95),
            ("name", "Student Name", 170),
            ("status", "Status", 75)
        ]:
            self.student_tree.heading(col, text=title)
            self.student_tree.column(col, width=width, anchor="w")

        self.student_tree.pack(fill="both", expand=True)
        self.student_tree.bind("<<TreeviewSelect>>", self.select_student)

        # Right: Tabs Notebook
        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True)
        self.tabs.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        self.profile_tab = ttk.Frame(self.tabs, padding=10)
        self.academic_tab = ttk.Frame(self.tabs, padding=10)
        self.graph_tab = ttk.Frame(self.tabs, padding=10)
        self.seminar_tab = ttk.Frame(self.tabs, padding=10)
        self.activity_tab = ttk.Frame(self.tabs, padding=10)
        self.drop_tab = ttk.Frame(self.tabs, padding=10)

        for tab, title in [
            (self.profile_tab, "Profile & Eligibility"),
            (self.academic_tab, "Subject Marks"),
            (self.graph_tab, "Progression Graph"),
            (self.seminar_tab, "Seminars"),
            (self.activity_tab, "Activities"),
            (self.drop_tab, "Gap / Drop Years")
        ]:
            self.tabs.add(tab, text=title)

        # Tab 1: Profile & Eligibility
        self.setup_profile_tab()

        # Tab 2: Academic Marks
        self.setup_marks_tab()

        # Tab 3: Progression Graph
        self.setup_graph_tab()

        # Tab 4: Seminars Tab
        self.setup_seminars_tab()

        # Tab 5: Activities Tab
        self.setup_activities_tab()

        # Tab 6: Drop / Gap Years Tab
        self.setup_drop_tab()

        # Footer
        self.footer = ttk.Label(
            self.root,
            text="Connected to MySQL | Ready | Select a student to view and manage ledger",
            anchor="w", padding=6
        )
        self.footer.pack(fill="x")

    def on_tab_changed(self, event=None):
        """Refreshes the active tab when clicked by user."""
        if not self.student_id:
            return
        try:
            current_idx = self.tabs.index(self.tabs.select())
            if current_idx == 0:
                self.load_profile()
            elif current_idx == 1:
                self.load_marks()
            elif current_idx == 2:
                self.load_graph()
            elif current_idx == 3:
                self.load_seminars()
            elif current_idx == 4:
                self.load_activities()
            elif current_idx == 5:
                self.load_drop_years()
        except Exception:
            pass

    # ---------------- TAB SETUP METHODS ----------------

    def setup_profile_tab(self):
        btn_bar = ttk.Frame(self.profile_tab)
        btn_bar.pack(fill="x", pady=(0, 6))
        ttk.Button(btn_bar, text="✏️ Edit Profile", command=self.edit_student_dialog).pack(side="left", padx=2)
        self.eligibility_btn = ttk.Button(
            btn_bar, text="📋 Submit Ledger (TE Regular Check)", command=self.submit_ledger
        )
        self.eligibility_btn.pack(side="left", padx=8)

        self.profile_text = tk.Text(
            self.profile_tab, height=18, wrap="word",
            font=("Consolas", 10), state="disabled", bg="#FDFDFD"
        )
        self.profile_text.pack(fill="both", expand=True)

    def setup_marks_tab(self):
        ctrls = ttk.Frame(self.academic_tab)
        ctrls.pack(fill="x", pady=(0, 6))
        ttk.Button(ctrls, text="+ Add / Update Subject Mark", command=self.add_mark_dialog).pack(side="left", padx=2)
        ttk.Button(ctrls, text="Recalculate SGPA/CGPA", command=self.recalculate_student_gpa).pack(side="left", padx=6)
        
        # Uses exact 6 columns from original schema
        self.marks_tree = self.make_table(
            self.academic_tab,
            ("semester", "subject", "type", "internal", "external", "lab"),
            ("Semester", "Subject", "Type", "Internal", "External", "Lab"),
            widths=[80, 240, 90, 85, 85, 85]
        )

    def setup_graph_tab(self):
        ctrls = ttk.Frame(self.graph_tab)
        ctrls.pack(fill="x", pady=(0, 4))
        ttk.Button(ctrls, text="🔄 Refresh Graph", command=self.load_graph).pack(side="left")
        self.graph_area = ttk.Frame(self.graph_tab)
        self.graph_area.pack(fill="both", expand=True)
        # Display initial prompt before any student is selected
        self.show_initial_graph_prompt()

    def show_initial_graph_prompt(self):
        for widget in self.graph_area.winfo_children():
            widget.destroy()
        fig = Figure(figsize=(7, 4), dpi=100)
        ax = fig.add_subplot(111)
        ax.text(
            0.5, 0.5,
            "No student selected.\n\nPlease select a student from the Student Directory on the left.",
            ha="center", va="center", transform=ax.transAxes, fontsize=11, color="#666666"
        )
        ax.set_axis_off()
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self.graph_area)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def setup_seminars_tab(self):
        ctrls = ttk.Frame(self.seminar_tab)
        ctrls.pack(fill="x", pady=(0, 6))
        ttk.Button(ctrls, text="+ Add Seminar", command=self.add_seminar_dialog).pack(side="left", padx=2)
        
        self.seminar_filter = tk.StringVar(value="All")
        ttk.Label(ctrls, text="Filter Type:").pack(side="left", padx=(12, 2))
        s_box = ttk.Combobox(
            ctrls, textvariable=self.seminar_filter,
            values=["All", "Internal", "External"],
            state="readonly", width=14
        )
        s_box.pack(side="left", padx=4)
        s_box.bind("<<ComboboxSelected>>", lambda e: self.load_seminars())

        # Exact 4 columns from original schema
        self.seminar_tree = self.make_table(
            self.seminar_tab,
            ("name", "type", "date", "certificate"),
            ("Seminar Name", "Type", "Event Date", "Certificate Reference"),
            widths=[260, 100, 110, 180]
        )

    def setup_activities_tab(self):
        ctrls = ttk.Frame(self.activity_tab)
        ctrls.pack(fill="x", pady=(0, 6))
        ttk.Button(ctrls, text="+ Add Activity", command=self.add_activity_dialog).pack(side="left", padx=2)

        self.activity_filter = tk.StringVar(value="All")
        ttk.Label(ctrls, text="Filter Category:").pack(side="left", padx=(12, 2))
        a_box = ttk.Combobox(
            ctrls, textvariable=self.activity_filter,
            values=["All", "Technical", "Co-curricular", "Extra-curricular"],
            state="readonly", width=18
        )
        a_box.pack(side="left", padx=4)
        a_box.bind("<<ComboboxSelected>>", lambda e: self.load_activities())

        # Exact 4 columns from original schema
        self.activity_tree = self.make_table(
            self.activity_tab,
            ("name", "category", "date", "description"),
            ("Activity Name", "Category", "Event Date", "Description"),
            widths=[230, 130, 110, 250]
        )

    def setup_drop_tab(self):
        ctrls = ttk.Frame(self.drop_tab)
        ctrls.pack(fill="x", pady=(0, 6))
        ttk.Button(ctrls, text="+ Add Gap / Drop Year", command=self.add_drop_year_dialog).pack(side="left", padx=2)

        # Exact 3 columns from original schema
        self.drop_tree = self.make_table(
            self.drop_tab,
            ("start", "end", "reason"),
            ("Start Year", "End Year", "Reason for Gap / Drop"),
            widths=[110, 110, 360]
        )

    def make_table(self, parent, columns, headings, widths=None):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=columns, show="headings")

        for idx, (col, heading) in enumerate(zip(columns, headings)):
            tree.heading(col, text=heading)
            w = widths[idx] if widths and idx < len(widths) else 120
            tree.column(col, width=w, anchor="w")

        ybar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        xbar = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)

        tree.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        return tree

    def clear_table(self, tree):
        for item in tree.get_children():
            tree.delete(item)

    # ---------------- DATA LOADING METHODS ----------------

    def load_students(self):
        self.clear_table(self.student_tree)
        search = self.search_entry.get().strip()
        try:
            # Searches both full_name AND roll_number
            rows = self.query(
                """SELECT student_id, roll_number, full_name, current_status
                   FROM students
                   WHERE full_name LIKE %s OR roll_number LIKE %s
                   ORDER BY full_name""",
                (f"%{search}%", f"%{search}%")
            )
            for student_id, roll, name, status in rows:
                self.student_tree.insert(
                    "", "end", iid=str(student_id),
                    values=(roll, name, status or "Active")
                )
            if not rows:
                self.show_profile_text("No students found.")
            else:
                # Auto-select the first student if nothing is currently selected
                children = self.student_tree.get_children()
                if children and not self.student_id:
                    self.student_tree.selection_set(children[0])
                    self.student_tree.focus(children[0])
                    self.select_student()
        except mysql.connector.Error as err:
            messagebox.showerror("Database Error", str(err))

    def show_all_students(self):
        self.search_entry.delete(0, "end")
        self.load_students()

    def select_student(self, event=None):
        selected = self.student_tree.selection()
        if not selected:
            return
        self.student_id = int(selected[0])
        values = self.student_tree.item(selected[0], "values")
        self.student_roll = values[0]
        self.student_name = values[1]

        # Load each tab independently with safety guards
        for loader in (
            self.load_profile,
            self.load_marks,
            self.load_graph,
            self.load_seminars,
            self.load_activities,
            self.load_drop_years
        ):
            try:
                loader()
            except Exception as e:
                print(f"Error loading {loader.__name__}: {e}")

        self.footer.config(text=f"Selected: {self.student_name} ({self.student_roll})")

    def show_profile_text(self, text):
        self.profile_text.configure(state="normal")
        self.profile_text.delete("1.0", "end")
        self.profile_text.insert("1.0", text)
        self.profile_text.configure(state="disabled")

    def load_profile(self):
        if not self.student_id:
            return

        cursor = self.conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM students WHERE student_id=%s", (self.student_id,))
        record = cursor.fetchone()
        cursor.close()

        if not record:
            return

        self.student_data = record

        # Perform TE Regular Attendance Roll Eligibility check
        eligible, elig_msg, elig_details = StudentEligibilityChecker.check_te_regular_eligibility(record)

        header_line = "=" * 60
        text = f"{header_line}\nSTUDENT PROFILE: {record.get('full_name')} ({record.get('roll_number')})\n{header_line}\n\n"
        text += f"Roll Number      : {record.get('roll_number')}\n"
        text += f"Full Name        : {record.get('full_name')}\n"
        text += f"Date of Birth    : {record.get('date_of_birth') or 'Not entered'}\n"
        text += f"Email Address    : {record.get('email') or 'Not entered'}\n"
        text += f"Admission Year   : {record.get('admission_year') or 'Not entered'}\n"
        text += f"10th Percentage  : {record.get('tenth_percentage') or 'Not entered'} %\n"
        text += f"12th Percentage  : {record.get('twelfth_percentage') or 'Not entered'} %\n"
        text += f"Current Status   : {record.get('current_status') or 'Active'}\n"

        # Display 3NF / TE extended fields if present
        if "year_of_study" in record:
            text += f"Year of Study    : {record.get('year_of_study') or 'Not assigned'}\n"
        if "student_type" in record:
            text += f"Student Type     : {record.get('student_type') or 'Regular'}\n"
        if "is_on_attendance_roll" in record:
            roll_status = "On Roll (Active)" if record.get("is_on_attendance_roll") == 1 else "Not on current roll"
            text += f"Attendance Roll  : {roll_status}\n"
        if "submission_status" in record:
            text += f"Submission Status: {record.get('submission_status') or 'Draft'}\n"

        text += f"\n{header_line}\nTE REGULAR ATTENDANCE ROLL VERIFICATION\n{header_line}\n"
        if eligible:
            text += f"STATUS: [ELIGIBLE]\n{elig_msg}\n"
            text += "-> This student is authorized to submit ledger records.\n"
        else:
            text += f"STATUS: [INELIGIBLE / PENDING]\nReason: {elig_msg}\n"
            if elig_details.get("status") == "INSUFFICIENT_DATA":
                text += "\nNote: Database schema does not yet include year_of_study, student_type, or\n"
                text += "attendance roll fields. See schema_upgrade_proposal.sql to safely enable these.\n"

        self.show_profile_text(text)

    def load_marks(self):
        self.clear_table(self.marks_tree)
        if not self.student_id:
            self.marks_tree.insert("", "end", values=("-", "Select a student from directory to view marks", "-", "-", "-", "-"))
            return

        try:
            # Query matches original schema exactly (6 columns)
            rows = self.query(
                """SELECT s.semester_number, sub.subject_name, sub.subject_type,
                          r.internal_marks, r.external_marks, r.lab_marks
                   FROM subject_results r
                   JOIN semesters s ON r.semester_id=s.semester_id
                   JOIN subjects sub ON r.subject_id=sub.subject_id
                   WHERE s.student_id=%s
                   ORDER BY s.semester_number, sub.subject_name""",
                (self.student_id,)
            )
            if not rows:
                self.marks_tree.insert(
                    "", "end",
                    values=("-", f"No subject marks recorded for {self.student_name}", "-", "-", "-", "-")
                )
                return

            for row in rows:
                display_row = [
                    row[0], row[1], row[2],
                    row[3] if row[3] is not None else "-",
                    row[4] if row[4] is not None else "-",
                    row[5] if row[5] is not None else "-"
                ]
                self.marks_tree.insert("", "end", values=display_row)
        except mysql.connector.Error as err:
            self.marks_tree.insert("", "end", values=("-", f"Database error loading marks: {err}", "-", "-", "-", "-"))

    def load_graph(self):
        for widget in self.graph_area.winfo_children():
            widget.destroy()

        if not self.student_id:
            self.show_initial_graph_prompt()
            return

        try:
            rows = self.query(
                """SELECT semester_number, sgpa, cgpa
                   FROM semesters
                   WHERE student_id=%s
                   ORDER BY semester_number""",
                (self.student_id,)
            )

            # Filter out records where both SGPA and CGPA are None
            valid_points = []
            if rows:
                for r in rows:
                    sem = r[0]
                    sgpa = float(r[1]) if r[1] is not None else None
                    cgpa = float(r[2]) if r[2] is not None else None
                    if sgpa is not None or cgpa is not None:
                        valid_points.append((sem, sgpa, cgpa))

            fig = Figure(figsize=(7, 4), dpi=100)
            ax = fig.add_subplot(111)

            if valid_points:
                semesters = [p[0] for p in valid_points]
                sgpa_vals = [p[1] for p in valid_points]
                cgpa_vals = [p[2] for p in valid_points]

                ax.plot(semesters, sgpa_vals, marker="o", linewidth=2, label="SGPA", color="#1F4E79")
                ax.plot(semesters, cgpa_vals, marker="s", linewidth=2, label="CGPA", color="#C00000")
                ax.set_xticks(range(1, 9))
                ax.set_ylim(0, 10)
                ax.set_xlabel("Semester", fontsize=10, fontweight="bold")
                ax.set_ylabel("Grade Point Average", fontsize=10, fontweight="bold")
                ax.set_title(f"Academic Progression: {self.student_name} ({self.student_roll})", fontsize=11, fontweight="bold")
                ax.grid(True, linestyle="--", alpha=0.5)
                ax.legend(loc="lower right")
            else:
                # Clear empty-state message when no semester results exist
                ax.text(
                    0.5, 0.5,
                    f"No semester progression data available for {self.student_name}.\n\n"
                    "To display the progression graph, enter subject marks under the 'Subject Marks' tab\n"
                    "and click 'Recalculate SGPA/CGPA'.",
                    ha="center", va="center", transform=ax.transAxes, fontsize=11, color="#444444"
                )
                ax.set_axis_off()

            fig.tight_layout()
            canvas = FigureCanvasTkAgg(fig, master=self.graph_area)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)
        except mysql.connector.Error as err:
            lbl = ttk.Label(self.graph_area, text=f"Database error loading progression: {err}", font=("Arial", 10), foreground="red")
            lbl.pack(pady=20)

    def load_seminars(self):
        self.clear_table(self.seminar_tree)
        if not self.student_id:
            self.seminar_tree.insert("", "end", values=("Select a student from directory to view seminars", "-", "-", "-"))
            return

        filter_value = self.seminar_filter.get()
        try:
            sql = """SELECT seminar_name, seminar_type, event_date, certificate_reference
                     FROM seminars WHERE student_id=%s"""
            params = [self.student_id]
            if filter_value != "All":
                sql += " AND TRIM(LOWER(seminar_type))=%s"
                params.append(filter_value.lower())
            sql += " ORDER BY event_date DESC"

            rows = self.query(sql, tuple(params))
            if not rows:
                empty_msg = f"No seminars recorded for {self.student_name}"
                if filter_value != "All":
                    empty_msg += f" (Filter: {filter_value})"
                self.seminar_tree.insert("", "end", values=(empty_msg, filter_value if filter_value != "All" else "-", "-", "-"))
                return

            for row in rows:
                display_row = [
                    row[0], row[1],
                    str(row[2]) if row[2] else "-",
                    row[3] or "-"
                ]
                self.seminar_tree.insert("", "end", values=display_row)
        except mysql.connector.Error as err:
            self.seminar_tree.insert("", "end", values=(f"Database error loading seminars: {err}", "-", "-", "-"))

    def load_activities(self):
        self.clear_table(self.activity_tree)
        if not self.student_id:
            self.activity_tree.insert("", "end", values=("Select a student from directory to view activities", "-", "-", "-"))
            return

        filter_value = self.activity_filter.get()
        try:
            sql = """SELECT activity_name, category, activity_date, description
                     FROM activities WHERE student_id=%s"""
            params = [self.student_id]
            if filter_value != "All":
                sql += " AND TRIM(LOWER(category))=%s"
                params.append(filter_value.lower())
            sql += " ORDER BY activity_date DESC"

            rows = self.query(sql, tuple(params))
            if not rows:
                empty_msg = f"No activities recorded for {self.student_name}"
                if filter_value != "All":
                    empty_msg += f" (Category: {filter_value})"
                self.activity_tree.insert("", "end", values=(empty_msg, filter_value if filter_value != "All" else "-", "-", "-"))
                return

            for row in rows:
                display_row = [
                    row[0], row[1],
                    str(row[2]) if row[2] else "-",
                    row[3] or "-"
                ]
                self.activity_tree.insert("", "end", values=display_row)
        except mysql.connector.Error as err:
            self.activity_tree.insert("", "end", values=(f"Database error loading activities: {err}", "-", "-", "-"))

    def load_drop_years(self):
        self.clear_table(self.drop_tree)
        if not self.student_id:
            self.drop_tree.insert("", "end", values=("-", "-", "Select a student from directory to view gap years"))
            return

        try:
            rows = self.query(
                """SELECT start_year, end_year, reason
                   FROM drop_years WHERE student_id=%s
                   ORDER BY start_year""",
                (self.student_id,)
            )
            if not rows:
                self.drop_tree.insert(
                    "", "end",
                    values=("-", "-", f"No gap or drop years recorded for {self.student_name} (Continuous academic progression)")
                )
                return

            for row in rows:
                self.drop_tree.insert("", "end", values=row)
        except mysql.connector.Error as err:
            self.drop_tree.insert("", "end", values=("-", "-", f"Database error loading gap years: {err}"))

    # ---------------- ACTIONS & CRUD DIALOGS ----------------

    def submit_ledger(self):
        if not self.student_id:
            messagebox.showinfo("Select Student", "Please select a student record first.")
            return

        eligible, msg, details = StudentEligibilityChecker.check_te_regular_eligibility(self.student_data)
        if not eligible:
            messagebox.showwarning("Submission Blocked", f"Ledger submission rejected:\n\n{msg}")
            return

        if "submission_status" in self.student_data:
            ok, err = self.execute_dml(
                "UPDATE students SET submission_status='Submitted' WHERE student_id=%s",
                (self.student_id,)
            )
            if ok:
                messagebox.showinfo("Success", f"Ledger submitted successfully for {self.student_name}!")
                self.load_profile()
            else:
                messagebox.showerror("Error", f"Could not update status: {err}")
        else:
            messagebox.showinfo(
                "Eligibility Verified",
                f"Student {self.student_name} passed all TE Regular Attendance Roll criteria!\n\n"
                "(Note: Run schema_upgrade_proposal.sql to enable the persistent submission_status column)."
            )

    def recalculate_student_gpa(self):
        """Recalculate SGPA/CGPA from saved marks and refresh the graph."""
        if not self.student_id:
            messagebox.showinfo("Select Student", "Please select a student record first.")
            return
        try:
            sem_rows = self.query(
                "SELECT semester_id, semester_number FROM semesters WHERE student_id=%s ORDER BY semester_number",
                (self.student_id,)
            )
            if not sem_rows:
                # Recover semester IDs from any saved subject results if the schema/query was inconsistent.
                messagebox.showwarning("No Semester Records", "Marks are visible but no semester record was found. Please reopen the app after applying the latest patch.")
                return

            sgpa_list = []
            updated = 0
            for sem_id, sem_num in sem_rows:
                marks_rows = self.query(
                    "SELECT internal_marks, external_marks, lab_marks FROM subject_results WHERE semester_id=%s",
                    (sem_id,)
                )
                if not marks_rows:
                    continue
                points = []
                for internal, external, lab in marks_rows:
                    total = float(internal or 0) + float(external or 0) + float(lab or 0)
                    points.append(min(10.0, max(0.0, total / 10.0)))
                if not points:
                    continue
                sgpa = round(sum(points) / len(points), 2)
                sgpa_list.append((sem_num, sgpa))
                cgpa = round(sum(v for _, v in sgpa_list) / len(sgpa_list), 2)
                ok, result = self.execute_dml(
                    "UPDATE semesters SET sgpa=%s, cgpa=%s WHERE semester_id=%s",
                    (sgpa, cgpa, sem_id)
                )
                if ok:
                    updated += 1
                else:
                    raise RuntimeError(str(result))

            self.load_graph()
            self.load_marks()
            if updated:
                messagebox.showinfo("Updated", f"SGPA/CGPA recalculated for {updated} semester(s).")
            else:
                messagebox.showwarning("No Marks", "Semester records exist, but no saved subject marks were found to calculate SGPA/CGPA.")
        except Exception as err:
            messagebox.showerror("SGPA/CGPA Error", f"Could not recalculate SGPA/CGPA:\n{err}")

    def add_student(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Student")
        dialog.geometry("450x420")
        dialog.transient(self.root)
        dialog.grab_set()

        fields = [
            ("Roll Number", "roll"),
            ("Full Name", "name"),
            ("Admission Year (e.g. 2022)", "year"),
            ("Email (optional)", "email"),
            ("10th Percentage (optional)", "tenth"),
            ("12th Percentage (optional)", "twelfth"),
            ("Year of Study (FE/SE/TE/BE)", "yos"),
            ("Student Type (Regular/DSE)", "st_type")
        ]
        entries = {}
        for i, (label, key) in enumerate(fields):
            ttk.Label(dialog, text=label).grid(row=i, column=0, padx=10, pady=6, sticky="w")
            entry = ttk.Entry(dialog, width=28)
            entry.grid(row=i, column=1, padx=10, pady=6)
            if key == "yos":
                entry.insert(0, "TE")
            elif key == "st_type":
                entry.insert(0, "Regular")
            entries[key] = entry

        def save():
            roll = entries["roll"].get().strip()
            name = entries["name"].get().strip()
            year = entries["year"].get().strip()
            email = entries["email"].get().strip() or None
            tenth = entries["tenth"].get().strip() or None
            twelfth = entries["twelfth"].get().strip() or None
            yos = entries["yos"].get().strip() or "TE"
            st_type = entries["st_type"].get().strip() or "Regular"

            if not roll or not name or not year:
                messagebox.showwarning("Required Fields", "Roll number, name, and admission year are required.", parent=dialog)
                return

            try:
                year_val = int(year)
                tenth_val = float(tenth) if tenth else None
                twelfth_val = float(twelfth) if twelfth else None

                cols = ["roll_number", "full_name", "admission_year", "email",
                        "tenth_percentage", "twelfth_percentage", "current_status"]
                vals = [roll, name, year_val, email, tenth_val, twelfth_val, "Active"]

                if "year_of_study" in self.available_student_columns:
                    cols.extend(["year_of_study", "student_type", "is_on_attendance_roll"])
                    vals.extend([yos, st_type, 1])

                placeholders = ", ".join(["%s"] * len(vals))
                sql = f"INSERT INTO students ({', '.join(cols)}) VALUES ({placeholders})"

                ok, res = self.execute_dml(sql, tuple(vals))
                if ok:
                    dialog.destroy()
                    self.search_entry.delete(0, "end")
                    self.load_students()
                    messagebox.showinfo("Saved", "Student record added successfully.")
                else:
                    messagebox.showerror("Error", f"Could not save student:\n{res}", parent=dialog)
            except ValueError as ve:
                messagebox.showerror("Invalid Input", str(ve), parent=dialog)

        ttk.Button(dialog, text="Save Student", command=save).grid(row=len(fields), column=0, columnspan=2, pady=15)

    def edit_student_dialog(self):
        if not self.student_id or not self.student_data:
            messagebox.showinfo("Select Student", "Please select a student record to edit.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Profile: {self.student_name}")
        dialog.geometry("450x380")
        dialog.transient(self.root)
        dialog.grab_set()

        fields = [
            ("Full Name", "full_name"),
            ("Email", "email"),
            ("10th Percentage", "tenth_percentage"),
            ("12th Percentage", "twelfth_percentage"),
            ("Current Status", "current_status")
        ]
        entries = {}
        for i, (label, key) in enumerate(fields):
            ttk.Label(dialog, text=label).grid(row=i, column=0, padx=10, pady=8, sticky="w")
            entry = ttk.Entry(dialog, width=28)
            val = self.student_data.get(key)
            if val is not None:
                entry.insert(0, str(val))
            entry.grid(row=i, column=1, padx=10, pady=8)
            entries[key] = entry

        def save_changes():
            name = entries["full_name"].get().strip()
            email = entries["email"].get().strip() or None
            tenth = entries["tenth_percentage"].get().strip() or None
            twelfth = entries["twelfth_percentage"].get().strip() or None
            status = entries["current_status"].get().strip() or "Active"

            if not name:
                messagebox.showwarning("Required", "Full name cannot be empty.", parent=dialog)
                return

            try:
                t_val = float(tenth) if tenth else None
                tw_val = float(twelfth) if twelfth else None
                ok, res = self.execute_dml(
                    """UPDATE students
                       SET full_name=%s, email=%s, tenth_percentage=%s,
                           twelfth_percentage=%s, current_status=%s
                       WHERE student_id=%s""",
                    (name, email, t_val, tw_val, status, self.student_id)
                )
                if ok:
                    dialog.destroy()
                    self.load_students()
                    self.load_profile()
                    messagebox.showinfo("Saved", "Student profile updated successfully.")
                else:
                    messagebox.showerror("Error", f"Update failed: {res}", parent=dialog)
            except ValueError as ve:
                messagebox.showerror("Invalid Input", str(ve), parent=dialog)

        ttk.Button(dialog, text="Save Changes", command=save_changes).grid(row=len(fields), column=0, columnspan=2, pady=15)

    def add_mark_dialog(self):
        if not self.student_id:
            messagebox.showinfo("Select Student", "Please select a student record first.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Add/Update Marks: {self.student_name}")
        dialog.geometry("450x320")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Semester (1-8):").grid(row=0, column=0, padx=10, pady=6, sticky="w")
        sem_spin = ttk.Spinbox(dialog, from_=1, to=8, width=10)
        sem_spin.set(5)
        sem_spin.grid(row=0, column=1, padx=10, pady=6, sticky="w")

        ttk.Label(dialog, text="Subject Name:").grid(row=1, column=0, padx=10, pady=6, sticky="w")
        sub_entry = ttk.Entry(dialog, width=28)
        sub_entry.grid(row=1, column=1, padx=10, pady=6)

        ttk.Label(dialog, text="Subject Type:").grid(row=2, column=0, padx=10, pady=6, sticky="w")
        type_combo = ttk.Combobox(dialog, values=["Theory", "Practical", "Elective"], state="readonly", width=15)
        type_combo.set("Theory")
        type_combo.grid(row=2, column=1, padx=10, pady=6, sticky="w")

        ttk.Label(dialog, text="Internal Marks:").grid(row=3, column=0, padx=10, pady=6, sticky="w")
        int_entry = ttk.Entry(dialog, width=15)
        int_entry.grid(row=3, column=1, padx=10, pady=6, sticky="w")

        ttk.Label(dialog, text="External Marks:").grid(row=4, column=0, padx=10, pady=6, sticky="w")
        ext_entry = ttk.Entry(dialog, width=15)
        ext_entry.grid(row=4, column=1, padx=10, pady=6, sticky="w")

        ttk.Label(dialog, text="Lab Marks:").grid(row=5, column=0, padx=10, pady=6, sticky="w")
        lab_entry = ttk.Entry(dialog, width=15)
        lab_entry.grid(row=5, column=1, padx=10, pady=6, sticky="w")

        def save():
            sub_name = sub_entry.get().strip()
            sub_type = type_combo.get().strip()
            sem_num = int(sem_spin.get())
            int_m = int_entry.get().strip() or None
            ext_m = ext_entry.get().strip() or None
            lab_m = lab_entry.get().strip() or None

            if not sub_name:
                messagebox.showwarning("Required", "Subject name is required.", parent=dialog)
                return

            try:
                int_val = float(int_m) if int_m else None
                ext_val = float(ext_m) if ext_m else None
                lab_val = float(lab_m) if lab_m else None

                # 1. Ensure semester row exists in semesters
                sem_row = self.query(
                    "SELECT semester_id FROM semesters WHERE student_id=%s AND semester_number=%s",
                    (self.student_id, sem_num)
                )
                if sem_row:
                    sem_id = sem_row[0][0]
                else:
                    ok, sem_id = self.execute_dml(
                        "INSERT INTO semesters (student_id, semester_number, academic_year) VALUES (%s, %s, %s)",
                        (self.student_id, sem_num, 2026)
                    )

                # 2. Ensure subject row exists in subjects
                sub_row = self.query(
                    "SELECT subject_id FROM subjects WHERE subject_name=%s",
                    (sub_name,)
                )
                if sub_row:
                    sub_id = sub_row[0][0]
                else:
                    ok, sub_id = self.execute_dml(
                        "INSERT INTO subjects (subject_code, subject_name, semester_number, subject_type, max_marks) VALUES (%s, %s, %s, %s, %s)",
                        (f"S{sem_num}-{abs(hash(sub_name)) % 99999:05d}", sub_name, sem_num, sub_type, 100)
                    )

                # 3. Check if subject_results already exists for (semester_id, subject_id)
                res_row = self.query(
                    "SELECT * FROM subject_results WHERE semester_id=%s AND subject_id=%s",
                    (sem_id, sub_id)
                )
                if res_row:
                    self.execute_dml(
                        """UPDATE subject_results
                           SET internal_marks=%s, external_marks=%s, lab_marks=%s
                           WHERE semester_id=%s AND subject_id=%s""",
                        (int_val, ext_val, lab_val, sem_id, sub_id)
                    )
                else:
                    self.execute_dml(
                        """INSERT INTO subject_results
                           (semester_id, subject_id, internal_marks, external_marks, lab_marks)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (sem_id, sub_id, int_val, ext_val, lab_val)
                    )

                dialog.destroy()
                self.load_marks()
                self.recalculate_student_gpa()
                messagebox.showinfo("Saved", "Subject marks saved and progression updated.")
            except ValueError as ve:
                messagebox.showerror("Invalid Input", str(ve), parent=dialog)

        ttk.Button(dialog, text="Save Marks", command=save).grid(row=6, column=0, columnspan=2, pady=15)

    def add_seminar_dialog(self):
        if not self.student_id:
            messagebox.showinfo("Select Student", "Please select a student record first.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Add Seminar: {self.student_name}")
        dialog.geometry("450x280")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Seminar Name:").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        name_entry = ttk.Entry(dialog, width=28)
        name_entry.grid(row=0, column=1, padx=10, pady=8)

        ttk.Label(dialog, text="Seminar Type:").grid(row=1, column=0, padx=10, pady=8, sticky="w")
        type_combo = ttk.Combobox(dialog, values=["Internal", "External"], state="readonly", width=15)
        type_combo.set("Internal")
        type_combo.grid(row=1, column=1, padx=10, pady=8, sticky="w")

        ttk.Label(dialog, text="Event Date (YYYY-MM-DD):").grid(row=2, column=0, padx=10, pady=8, sticky="w")
        date_entry = ttk.Entry(dialog, width=18)
        date_entry.grid(row=2, column=1, padx=10, pady=8, sticky="w")

        ttk.Label(dialog, text="Certificate Ref:").grid(row=3, column=0, padx=10, pady=8, sticky="w")
        cert_entry = ttk.Entry(dialog, width=28)
        cert_entry.grid(row=3, column=1, padx=10, pady=8)

        def save():
            name = name_entry.get().strip()
            s_type = type_combo.get().strip()
            dt = date_entry.get().strip() or None
            cert = cert_entry.get().strip() or None

            if not name:
                messagebox.showwarning("Required", "Seminar name is required.", parent=dialog)
                return

            ok, res = self.execute_dml(
                """INSERT INTO seminars
                   (student_id, seminar_name, seminar_type, event_date, certificate_reference)
                   VALUES (%s, %s, %s, %s, %s)""",
                (self.student_id, name, s_type, dt, cert)
            )
            if ok:
                dialog.destroy()
                self.load_seminars()
                messagebox.showinfo("Saved", "Seminar record added.")
            else:
                messagebox.showerror("Error", f"Could not save seminar: {res}", parent=dialog)

        ttk.Button(dialog, text="Save Seminar", command=save).grid(row=4, column=0, columnspan=2, pady=15)

    def add_activity_dialog(self):
        if not self.student_id:
            messagebox.showinfo("Select Student", "Please select a student record first.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Add Activity: {self.student_name}")
        dialog.geometry("450x280")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Activity Name:").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        name_entry = ttk.Entry(dialog, width=28)
        name_entry.grid(row=0, column=1, padx=10, pady=8)

        ttk.Label(dialog, text="Category:").grid(row=1, column=0, padx=10, pady=8, sticky="w")
        cat_combo = ttk.Combobox(
            dialog, values=["Technical", "Co-curricular", "Extra-curricular"],
            state="readonly", width=18
        )
        cat_combo.set("Technical")
        cat_combo.grid(row=1, column=1, padx=10, pady=8, sticky="w")

        ttk.Label(dialog, text="Date (YYYY-MM-DD):").grid(row=2, column=0, padx=10, pady=8, sticky="w")
        date_entry = ttk.Entry(dialog, width=18)
        date_entry.grid(row=2, column=1, padx=10, pady=8, sticky="w")

        ttk.Label(dialog, text="Description:").grid(row=3, column=0, padx=10, pady=8, sticky="w")
        desc_entry = ttk.Entry(dialog, width=28)
        desc_entry.grid(row=3, column=1, padx=10, pady=8)

        def save():
            name = name_entry.get().strip()
            cat = cat_combo.get().strip()
            dt = date_entry.get().strip() or None
            desc = desc_entry.get().strip() or None

            if not name:
                messagebox.showwarning("Required", "Activity name is required.", parent=dialog)
                return

            ok, res = self.execute_dml(
                """INSERT INTO activities
                   (student_id, activity_name, category, activity_date, description)
                   VALUES (%s, %s, %s, %s, %s)""",
                (self.student_id, name, cat, dt, desc)
            )
            if ok:
                dialog.destroy()
                self.load_activities()
                messagebox.showinfo("Saved", "Activity record added.")
            else:
                messagebox.showerror("Error", f"Could not save activity: {res}", parent=dialog)

        ttk.Button(dialog, text="Save Activity", command=save).grid(row=4, column=0, columnspan=2, pady=15)

    def add_drop_year_dialog(self):
        if not self.student_id:
            messagebox.showinfo("Select Student", "Please select a student record first.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Add Gap / Drop Year: {self.student_name}")
        dialog.geometry("450x250")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Start Year (YYYY):").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        start_entry = ttk.Entry(dialog, width=15)
        start_entry.grid(row=0, column=1, padx=10, pady=8, sticky="w")

        ttk.Label(dialog, text="End Year (YYYY):").grid(row=1, column=0, padx=10, pady=8, sticky="w")
        end_entry = ttk.Entry(dialog, width=15)
        end_entry.grid(row=1, column=1, padx=10, pady=8, sticky="w")

        ttk.Label(dialog, text="Reason:").grid(row=2, column=0, padx=10, pady=8, sticky="w")
        reason_entry = ttk.Entry(dialog, width=28)
        reason_entry.grid(row=2, column=1, padx=10, pady=8)

        def save():
            sy = start_entry.get().strip()
            ey = end_entry.get().strip()
            reason = reason_entry.get().strip()

            if not sy or not ey:
                messagebox.showwarning("Required", "Start and End years are required.", parent=dialog)
                return

            try:
                sy_val = int(sy)
                ey_val = int(ey)
                ok, res = self.execute_dml(
                    """INSERT INTO drop_years
                       (student_id, start_year, end_year, reason)
                       VALUES (%s, %s, %s, %s)""",
                    (self.student_id, sy_val, ey_val, reason)
                )
                if ok:
                    dialog.destroy()
                    self.load_drop_years()
                    messagebox.showinfo("Saved", "Gap / Drop year record added.")
                else:
                    messagebox.showerror("Error", f"Could not save: {res}", parent=dialog)
            except ValueError:
                messagebox.showerror("Invalid Input", "Years must be integers.", parent=dialog)

        ttk.Button(dialog, text="Save Gap Year", command=save).grid(row=3, column=0, columnspan=2, pady=15)

    # ---------------- CSV EXPORT & GOOGLE SHEETS ----------------

    def fetch_full_ledger_data(self):
        """Fetches normalized relational tables into a dictionary for export."""
        cursor = self.conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM students ORDER BY roll_number")
        students = cursor.fetchall()

        cursor.execute(
            """SELECT s.*, st.roll_number, st.full_name
               FROM semesters s
               JOIN students st ON s.student_id=st.student_id
               ORDER BY st.roll_number, s.semester_number"""
        )
        semesters = cursor.fetchall()

        cursor.execute(
            """SELECT s.semester_number, sub.subject_name, sub.subject_type,
                      r.internal_marks, r.external_marks, r.lab_marks,
                      st.roll_number, st.full_name
               FROM subject_results r
               JOIN semesters s ON r.semester_id=s.semester_id
               JOIN subjects sub ON r.subject_id=sub.subject_id
               JOIN students st ON s.student_id=st.student_id
               ORDER BY st.roll_number, s.semester_number, sub.subject_name"""
        )
        marks = cursor.fetchall()

        cursor.execute(
            """SELECT sm.*, st.roll_number, st.full_name
               FROM seminars sm
               JOIN students st ON sm.student_id=st.student_id
               ORDER BY st.roll_number, sm.event_date DESC"""
        )
        seminars = cursor.fetchall()

        cursor.execute(
            """SELECT a.*, st.roll_number, st.full_name
               FROM activities a
               JOIN students st ON a.student_id=st.student_id
               ORDER BY st.roll_number, a.activity_date DESC"""
        )
        activities = cursor.fetchall()

        cursor.execute(
            """SELECT d.*, st.roll_number, st.full_name
               FROM drop_years d
               JOIN students st ON d.student_id=st.student_id
               ORDER BY st.roll_number, d.start_year"""
        )
        drop_years = cursor.fetchall()
        cursor.close()

        return {
            "students": students,
            "semesters": semesters,
            "marks": marks,
            "seminars": seminars,
            "activities": activities,
            "drop_years": drop_years
        }

    def export_csv_dialog(self):
        """Exports validated UTF-8 CSV files with formula injection protection."""
        target_dir = filedialog.askdirectory(
            title="Select Directory for CSV Export",
            initialdir=os.path.abspath("exports") if os.path.exists("exports") else os.getcwd()
        )
        if not target_dir:
            return

        try:
            db_data = self.fetch_full_ledger_data()
            exporter = LedgerCSVExporter(target_dir)
            result = exporter.export_all(db_data)

            msg = (
                f"CSV Export Completed Successfully!\n\n"
                f"Output Folder: {target_dir}\n\n"
                f"Files Generated:\n"
                f"• 01_students.csv ({result['counts']['students']} rows)\n"
                f"• 02_semesters.csv ({result['counts']['semesters']} rows)\n"
                f"• 03_subject_marks.csv ({result['counts']['marks']} rows)\n"
                f"• 04_seminars.csv ({result['counts']['seminars']} rows)\n"
                f"• 05_activities.csv ({result['counts']['activities']} rows)\n"
                f"• 06_gap_drop_years.csv ({result['counts']['drop_years']} rows)\n"
                f"• HOW_TO_IMPORT_INTO_GOOGLE_SHEETS.txt\n\n"
                f"All CSVs are encoded in UTF-8 with BOM and protected against formula injection."
            )
            if result.get("validation_warnings"):
                msg += f"\n\nValidation Warnings ({len(result['validation_warnings'])}):\n"
                msg += "\n".join(result["validation_warnings"][:5])

            messagebox.showinfo("Export Successful", msg)
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export CSVs:\n{str(e)}")

    def show_sync_details_dialog(self, title: str, is_success: bool, message: str, parent=None):
        """Displays rich, selectable sync results or actionable error instructions."""
        dlg = tk.Toplevel(parent or self.root)
        dlg.title(title)
        dlg.geometry("580x440")
        dlg.minsize(500, 360)
        dlg.transient(parent or self.root)
        dlg.grab_set()

        hdr_bg = "#2E7D32" if is_success else "#C62828"
        hdr_frame = tk.Frame(dlg, bg=hdr_bg, pady=10)
        hdr_frame.pack(fill="x")
        icon = "✓" if is_success else "✗"
        tk.Label(
            hdr_frame,
            text=f"{icon} {title}",
            font=("Arial", 12, "bold"),
            bg=hdr_bg,
            fg="white"
        ).pack(padx=15, anchor="w")

        text_frame = ttk.Frame(dlg, padding=12)
        text_frame.pack(fill="both", expand=True)

        txt = tk.Text(text_frame, wrap="word", font=("Consolas", 9), bg="#F8F9FA", relief="solid", borderwidth=1)
        txt.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(text_frame, orient="vertical", command=txt.yview)
        sb.pack(side="right", fill="y")
        txt.configure(yscrollcommand=sb.set)

        txt.insert("1.0", message)
        txt.configure(state="disabled")

        btn_bar = ttk.Frame(dlg, padding=10)
        btn_bar.pack(fill="x")

        def copy_to_clipboard():
            dlg.clipboard_clear()
            dlg.clipboard_append(message)
            messagebox.showinfo("Copied", "Details copied to clipboard.", parent=dlg)

        ttk.Button(btn_bar, text="📋 Copy Details", command=copy_to_clipboard).pack(side="left", padx=5)

        sid_match = re.search(r"Spreadsheet ID:\s*([a-zA-Z0-9_-]+)", message)
        if sid_match:
            sid = sid_match.group(1)
            def open_browser():
                webbrowser.open(f"https://docs.google.com/spreadsheets/d/{sid}/edit")
            ttk.Button(btn_bar, text="🌐 Open Sheet in Browser", command=open_browser).pack(side="left", padx=5)

        ttk.Button(btn_bar, text="Close", command=dlg.destroy).pack(side="right", padx=5)

    def google_sheets_dialog(self):
        """Displays Google Sheets synchronization status, details, and controls."""
        ready, status_msg = self.sheets_service.is_configured()
        config = self.sheets_service.load_config()
        spreadsheet_id = config.get("spreadsheet_id", "")
        creds_path = self.sheets_service.resolve_credentials_path() or config.get("credentials_path", "")
        sa_email = self.sheets_service.get_service_account_email(creds_path) or "Not detected"

        dialog = tk.Toplevel(self.root)
        dialog.title("Google Sheets Synchronization")
        dialog.geometry("600x490")
        dialog.minsize(540, 440)
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Google Sheets One-Way Sync", font=("Arial", 12, "bold")).pack(anchor="w", padx=15, pady=(12, 4))

        status_frame = ttk.LabelFrame(dialog, text="Sync Status", padding=10)
        status_frame.pack(fill="x", padx=15, pady=4)

        status_text = "🟢 READY TO SYNC" if ready else "🟡 OFFLINE / NOT CONFIGURED"
        ttk.Label(status_frame, text=status_text, font=("Arial", 10, "bold")).pack(anchor="w")
        ttk.Label(status_frame, text=status_msg, wraplength=540, justify="left").pack(anchor="w", pady=(4, 0))

        # Configuration details frame
        cfg_frame = ttk.LabelFrame(dialog, text="Configuration & Credentials", padding=10)
        cfg_frame.pack(fill="x", padx=15, pady=4)

        # Spreadsheet ID row
        s_row = ttk.Frame(cfg_frame)
        s_row.pack(fill="x", pady=2)
        ttk.Label(s_row, text="Spreadsheet ID:", width=18, anchor="w", font=("Arial", 9, "bold")).pack(side="left")
        sid_ent = ttk.Entry(s_row)
        sid_ent.insert(0, spreadsheet_id or "(none)")
        sid_ent.configure(state="readonly")
        sid_ent.pack(side="left", fill="x", expand=True, padx=4)

        if spreadsheet_id:
            def open_sheet_link():
                webbrowser.open(f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit")
            ttk.Button(s_row, text="Open Link", command=open_sheet_link, width=10).pack(side="left")

        # Service Account Email row
        sa_row = ttk.Frame(cfg_frame)
        sa_row.pack(fill="x", pady=2)
        ttk.Label(sa_row, text="Service Account:", width=18, anchor="w", font=("Arial", 9, "bold")).pack(side="left")
        sa_ent = ttk.Entry(sa_row)
        sa_ent.insert(0, sa_email)
        sa_ent.configure(state="readonly")
        sa_ent.pack(side="left", fill="x", expand=True, padx=4)
        if sa_email and "Not detected" not in sa_email:
            def copy_sa():
                dialog.clipboard_clear()
                dialog.clipboard_append(sa_email)
                messagebox.showinfo("Copied", "Service account email copied to clipboard.", parent=dialog)
            ttk.Button(sa_row, text="Copy", command=copy_sa, width=6).pack(side="left")

        # Credentials File row
        cp_row = ttk.Frame(cfg_frame)
        cp_row.pack(fill="x", pady=2)
        ttk.Label(cp_row, text="Credentials File:", width=18, anchor="w", font=("Arial", 9, "bold")).pack(side="left")
        cp_ent = ttk.Entry(cp_row)
        cp_ent.insert(0, os.path.basename(creds_path) if creds_path else "(none)")
        cp_ent.configure(state="readonly")
        cp_ent.pack(side="left", fill="x", expand=True, padx=4)

        info_lbl = ttk.Label(
            dialog,
            text="Safety Notice: Student data is only uploaded when you click 'Push Changes'. "
                 "The service account must be invited as 'Editor' to your Google Spreadsheet.",
            wraplength=540, justify="left", font=("Arial", 8, "italic")
        )
        info_lbl.pack(padx=15, pady=6)

        # Action test / sync buttons
        act_box = ttk.Frame(dialog)
        act_box.pack(fill="x", padx=15, pady=6)

        def do_test_connection():
            ok, res_msg = self.sheets_service.test_connection()
            if ok:
                self.show_sync_details_dialog("Connection Verified", True, res_msg, parent=dialog)
            else:
                self.show_sync_details_dialog("Connection Test Failed", False, res_msg, parent=dialog)

        ttk.Button(act_box, text="🔍 Test Connection", command=do_test_connection).pack(side="left", padx=(0, 6))

        if ready:
            def do_sync():
                data = self.fetch_full_ledger_data()
                ok, res_msg = self.sheets_service.push_to_google_sheets(data)
                if ok:
                    self.show_sync_details_dialog("Sync Successful", True, res_msg, parent=dialog)
                else:
                    self.show_sync_details_dialog("Sync Failed", False, res_msg, parent=dialog)

            ttk.Button(act_box, text="🚀 Push Changes to Google Sheets", command=do_sync).pack(side="left", padx=6)

        # Bottom nav buttons
        btn_box = ttk.Frame(dialog)
        btn_box.pack(fill="x", padx=15, pady=(8, 12))

        ttk.Button(btn_box, text="📥 Use Validated CSV Export Instead", command=lambda: (dialog.destroy(), self.export_csv_dialog())).pack(side="left")
        ttk.Button(btn_box, text="Close", command=dialog.destroy).pack(side="right")

    def seed_demo_data_dialog(self):
        """Proposes inserting clearly labelled fictional demo students without touching real data."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Seed Fictional Demo Records")
        dialog.geometry("520x420")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Seed Fictional Demo Records", font=("Arial", 12, "bold")).pack(anchor="w", padx=15, pady=(12, 4))
        desc = (
            "This utility adds clearly labelled fictional demo students and academic records\n"
            "so you can demonstrate multi-student progression graphs, seminars, and activities.\n\n"
            "Safety Guarantees:\n"
            "• Every demo student has roll starting with DEMO- and name prefixed with [DEMO].\n"
            "• Never modifies, overwrites, or deletes your existing student records.\n"
            "• Checks before inserting so duplicate demo records are never created."
        )
        ttk.Label(dialog, text=desc, justify="left").pack(anchor="w", padx=15, pady=(0, 10))

        listbox = tk.Listbox(dialog, height=6)
        listbox.pack(fill="x", padx=15, pady=5)
        for s in DEMO_STUDENTS:
            listbox.insert("end", f"{s['roll_number']} | {s['full_name']} | {s['year_of_study']} ({s['student_type']})")

        def execute_demo_seed():
            inserted_count = 0
            for s in DEMO_STUDENTS:
                existing = self.query("SELECT student_id FROM students WHERE roll_number=%s", (s["roll_number"],))
                if existing:
                    continue

                cols = ["roll_number", "full_name", "date_of_birth", "email",
                        "admission_year", "tenth_percentage", "twelfth_percentage", "current_status"]
                vals = [s["roll_number"], s["full_name"], s["date_of_birth"], s["email"],
                        s["admission_year"], s["tenth_percentage"], s["twelfth_percentage"], s["current_status"]]

                if "year_of_study" in self.available_student_columns:
                    cols.extend(["year_of_study", "student_type", "is_on_attendance_roll"])
                    vals.extend([s["year_of_study"], s["student_type"], s["is_on_attendance_roll"]])

                placeholders = ", ".join(["%s"] * len(vals))
                sql = f"INSERT INTO students ({', '.join(cols)}) VALUES ({placeholders})"
                ok, st_id = self.execute_dml(sql, tuple(vals))
                if not ok:
                    continue

                inserted_count += 1

                # Insert Semesters
                sem_map = {}
                for sem in s.get("semesters", []):
                    ok_sem, sem_id = self.execute_dml(
                        "INSERT INTO semesters (student_id, semester_number, academic_year, sgpa, cgpa) VALUES (%s, %s, %s, %s, %s)",
                        (st_id, sem["semester_number"], 2026, sem["sgpa"], sem["cgpa"])
                    )
                    if ok_sem:
                        sem_map[sem["semester_number"]] = sem_id

                # Insert Marks
                for m in s.get("marks", []):
                    sem_id = sem_map.get(m["semester_number"])
                    if not sem_id:
                        continue
                    sub_row = self.query("SELECT subject_id FROM subjects WHERE subject_name=%s", (m["subject_name"],))
                    if sub_row:
                        sub_id = sub_row[0][0]
                    else:
                        ok_sub, sub_id = self.execute_dml(
                            "INSERT INTO subjects (subject_code, subject_name, semester_number, subject_type, max_marks) VALUES (%s, %s, %s, %s, %s)",
                            (f"S{m['semester_number']}-{abs(hash(m['subject_name'])) % 99999:05d}", m["subject_name"], m["semester_number"], m["subject_type"], 100)
                        )
                    self.execute_dml(
                        """INSERT INTO subject_results
                           (semester_id, subject_id, internal_marks, external_marks, lab_marks)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (sem_id, sub_id, m["internal_marks"], m["external_marks"], m["lab_marks"])
                    )

                # Insert Seminars
                for sm in s.get("seminars", []):
                    self.execute_dml(
                        """INSERT INTO seminars
                           (student_id, seminar_name, seminar_type, event_date, certificate_reference)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (st_id, sm["seminar_name"], sm["seminar_type"], sm["event_date"], sm["certificate_reference"])
                    )

                # Insert Activities
                for act in s.get("activities", []):
                    self.execute_dml(
                        """INSERT INTO activities
                           (student_id, activity_name, category, activity_date, description)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (st_id, act["activity_name"], act["category"], act["activity_date"], act["description"])
                    )

                # Insert Drop Years
                for dy in s.get("drop_years", []):
                    self.execute_dml(
                        """INSERT INTO drop_years (student_id, start_year, end_year, reason)
                           VALUES (%s, %s, %s, %s)""",
                        (st_id, dy["start_year"], dy["end_year"], dy["reason"])
                    )

            dialog.destroy()
            self.load_students()
            messagebox.showinfo("Demo Records Added", f"Added {inserted_count} fictional demo student records.\nYour real student records remain completely safe!")

        btn_box = ttk.Frame(dialog)
        btn_box.pack(fill="x", padx=15, pady=15)
        ttk.Button(btn_box, text="Confirm & Insert Demo Records", command=execute_demo_seed).pack(side="left")
        ttk.Button(btn_box, text="Cancel", command=dialog.destroy).pack(side="right")

    def close(self):
        if self.conn.is_connected():
            self.conn.close()
        self.root.destroy()


def main():
    root = tk.Tk()
    root.withdraw()
    password = simpledialog.askstring(
        "MySQL Login",
        "Enter your MySQL root password (it stays on your computer):",
        show="*",
        parent=root
    )
    if password is None:
        root.destroy()
        return
    root.deiconify()
    app = StudentLedgerApp(root, password)
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()


if __name__ == "__main__":
    main()
