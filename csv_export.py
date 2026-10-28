"""
csv_export.py
Module for validated, secure CSV export of Student Academic & Activity Ledger data.
Includes formula injection prevention, data validation, and UTF-8-sig encoding.
"""

import csv
import os
import re
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional


def sanitize_for_spreadsheet(value: Any) -> Any:
    """
    Prevents spreadsheet formula injection (CSV Injection / CWE-1236).
    If a text value begins with =, +, -, @, \\t, or \\r, prepend a single quote (')
    so that spreadsheet engines (Google Sheets, Microsoft Excel, LibreOffice)
    treat it as a literal string rather than an executable formula or command.
    """
    if value is None:
        return ""
    
    text = str(value)
    if not text:
        return ""

    # Check if first character is a dangerous formula prefix
    if text[0] in ('=', '+', '-', '@', '\t', '\r'):
        # If already single-quoted, leave it
        if text.startswith("'"):
            return text
        return f"'{text}"
    
    return text


def format_mark(val: Any) -> str:
    """
    Clearly distinguishes empty values (absent / not taken) from zero (0) marks.
    If val is None or empty string, returns empty string "".
    If val is numeric, returns formatted string (e.g., '0', '75', '82.5').
    """
    if val is None or val == "":
        return ""
    try:
        num = float(val)
        if num.is_integer():
            return str(int(num))
        return f"{num:.2f}"
    except (ValueError, TypeError):
        return sanitize_for_spreadsheet(val)


def format_date(val: Any) -> str:
    """Formats date into standard ISO YYYY-MM-DD or empty string."""
    if val is None or val == "":
        return ""
    if isinstance(val, (datetime,)):
        return val.strftime("%Y-%m-%d")
    text = str(val).strip()
    # Try parsing common formats
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return sanitize_for_spreadsheet(text)


class LedgerDataValidator:
    """Validates records before export to ensure relational and data integrity."""

    @staticmethod
    def validate_students(students: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        errors = []
        seen_rolls = set()
        for idx, s in enumerate(students, start=1):
            roll = str(s.get("roll_number", "")).strip()
            name = str(s.get("full_name", "")).strip()
            if not roll:
                errors.append(f"Student #{idx}: Missing roll number.")
            elif roll in seen_rolls:
                errors.append(f"Student #{idx}: Duplicate roll number '{roll}'.")
            else:
                seen_rolls.add(roll)

            if not name:
                errors.append(f"Student #{idx} (Roll: {roll}): Missing full name.")

            for pct_field in ("tenth_percentage", "twelfth_percentage"):
                val = s.get(pct_field)
                if val is not None and val != "":
                    try:
                        v = float(val)
                        if v < 0 or v > 100:
                            errors.append(f"Student {roll}: {pct_field} ({v}) out of valid range 0-100.")
                    except ValueError:
                        errors.append(f"Student {roll}: {pct_field} '{val}' is not a valid number.")

        return (len(errors) == 0, errors)

    @staticmethod
    def validate_marks(results: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        errors = []
        for idx, r in enumerate(results, start=1):
            student_ref = r.get("roll_number") or r.get("student_id") or f"Record #{idx}"
            sem = r.get("semester_number")
            if sem is not None and sem != "":
                try:
                    s_int = int(sem)
                    if s_int < 1 or s_int > 8:
                        errors.append(f"{student_ref}: Semester {s_int} out of standard range (1-8).")
                except ValueError:
                    errors.append(f"{student_ref}: Semester '{sem}' is not an integer.")

            for m_key in ("internal_marks", "external_marks", "lab_marks"):
                m_val = r.get(m_key)
                if m_val is not None and m_val != "":
                    try:
                        m_num = float(m_val)
                        if m_num < 0:
                            errors.append(f"{student_ref} (Sem {sem}, Subject {r.get('subject_name')}): {m_key} cannot be negative ({m_num}).")
                    except ValueError:
                        errors.append(f"{student_ref}: {m_key} '{m_val}' is not a valid numeric mark.")

        return (len(errors) == 0, errors)


class LedgerCSVExporter:
    """Exports student ledger data into separate, well-formed, UTF-8 CSV files."""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def write_csv(self, filename: str, headers: List[str], rows: List[List[Any]]) -> str:
        filepath = os.path.join(self.output_dir, filename)
        # Using utf-8-sig adds a byte order mark so Microsoft Excel and Google Sheets
        # reliably interpret special characters and commas properly without corruption.
        with open(filepath, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(headers)
            for row in rows:
                sanitized_row = [sanitize_for_spreadsheet(cell) for cell in row]
                writer.writerow(sanitized_row)
        return filepath

    def export_all(self, db_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Exports all tables from the dictionary of records.
        db_data expects keys: 'students', 'semesters', 'marks', 'seminars', 'activities', 'drop_years'
        Returns summary dictionary with counts and generated file paths.
        """
        results = {
            "success": True,
            "validation_warnings": [],
            "files": {},
            "counts": {}
        }

        # 1. Validate Students
        students = db_data.get("students", [])
        st_ok, st_errs = LedgerDataValidator.validate_students(students)
        if not st_ok:
            results["validation_warnings"].extend(st_errs)

        # 2. Validate Marks
        marks = db_data.get("marks", [])
        m_ok, m_errs = LedgerDataValidator.validate_marks(marks)
        if not m_ok:
            results["validation_warnings"].extend(m_errs)

        # 3. Export Students CSV
        st_headers = [
            "Roll Number", "Full Name", "Date of Birth", "Email",
            "Admission Year", "10th Percentage", "12th Percentage",
            "Current Status", "Year of Study", "Student Type", "Attendance Roll Status"
        ]
        st_rows = []
        for s in students:
            roll_status = s.get("attendance_roll_status")
            if not roll_status and "is_on_attendance_roll" in s:
                roll_val = s.get("is_on_attendance_roll")
                if roll_val in (1, True, "1"):
                    roll_status = "On Roll"
                elif roll_val in (0, False, "0"):
                    roll_status = "Not On Roll"
                else:
                    roll_status = ""
            st_rows.append([
                s.get("roll_number", ""),
                s.get("full_name", ""),
                format_date(s.get("date_of_birth")),
                s.get("email", ""),
                s.get("admission_year", ""),
                format_mark(s.get("tenth_percentage")),
                format_mark(s.get("twelfth_percentage")),
                s.get("current_status", "Active"),
                s.get("year_of_study", ""),
                s.get("student_type", "Regular"),
                roll_status or ""
            ])
        results["files"]["students"] = self.write_csv("01_students.csv", st_headers, st_rows)
        results["counts"]["students"] = len(st_rows)

        # 4. Export Semesters Summary CSV
        sem_headers = ["Roll Number", "Student Name", "Semester Number", "SGPA", "CGPA"]
        sem_rows = []
        for sem in db_data.get("semesters", []):
            sem_rows.append([
                sem.get("roll_number", ""),
                sem.get("full_name", ""),
                sem.get("semester_number", ""),
                format_mark(sem.get("sgpa")),
                format_mark(sem.get("cgpa"))
            ])
        results["files"]["semesters"] = self.write_csv("02_semesters.csv", sem_headers, sem_rows)
        results["counts"]["semesters"] = len(sem_rows)

        # 5. Export Subject Results / Marks CSV
        marks_headers = [
            "Roll Number", "Student Name", "Semester", "Subject Name",
            "Subject Type", "Internal Marks", "External Marks", "Lab Marks"
        ]
        marks_rows = []
        for m in marks:
            marks_rows.append([
                m.get("roll_number", ""),
                m.get("full_name", ""),
                m.get("semester_number", ""),
                m.get("subject_name", ""),
                m.get("subject_type", ""),
                format_mark(m.get("internal_marks")),
                format_mark(m.get("external_marks")),
                format_mark(m.get("lab_marks"))
            ])
        results["files"]["marks"] = self.write_csv("03_subject_marks.csv", marks_headers, marks_rows)
        results["counts"]["marks"] = len(marks_rows)

        # 6. Export Seminars CSV
        sem_headers = [
            "Roll Number", "Student Name", "Seminar Name",
            "Seminar Type", "Event Date", "Certificate Reference"
        ]
        sem_rows = []
        for sm in db_data.get("seminars", []):
            sem_rows.append([
                sm.get("roll_number", ""),
                sm.get("full_name", ""),
                sm.get("seminar_name", ""),
                sm.get("seminar_type", ""),
                format_date(sm.get("event_date")),
                sm.get("certificate_reference", "")
            ])
        results["files"]["seminars"] = self.write_csv("04_seminars.csv", sem_headers, sem_rows)
        results["counts"]["seminars"] = len(sem_rows)

        # 7. Export Activities CSV
        act_headers = [
            "Roll Number", "Student Name", "Activity Name",
            "Category", "Activity Date", "Description"
        ]
        act_rows = []
        for a in db_data.get("activities", []):
            act_rows.append([
                a.get("roll_number", ""),
                a.get("full_name", ""),
                a.get("activity_name", ""),
                a.get("category", ""),
                format_date(a.get("activity_date")),
                a.get("description", "")
            ])
        results["files"]["activities"] = self.write_csv("05_activities.csv", act_headers, act_rows)
        results["counts"]["activities"] = len(act_rows)

        # 8. Export Drop / Gap Years CSV
        drop_headers = [
            "Roll Number", "Student Name", "Start Year", "End Year", "Reason"
        ]
        drop_rows = []
        for d in db_data.get("drop_years", []):
            drop_rows.append([
                d.get("roll_number", ""),
                d.get("full_name", ""),
                d.get("start_year", ""),
                d.get("end_year", ""),
                d.get("reason", "")
            ])
        results["files"]["drop_years"] = self.write_csv("06_gap_drop_years.csv", drop_headers, drop_rows)
        results["counts"]["drop_years"] = len(drop_rows)

        # Also write an Import Guide README for Google Sheets
        guide_path = os.path.join(self.output_dir, "HOW_TO_IMPORT_INTO_GOOGLE_SHEETS.txt")
        with open(guide_path, "w", encoding="utf-8") as gf:
            gf.write(
                "===========================================================\n"
                "STUDENT ACADEMIC & ACTIVITY LEDGER - GOOGLE SHEETS IMPORT\n"
                "===========================================================\n\n"
                "These exported CSV files are encoded in UTF-8 with BOM and formula-injection\n"
                "protection, making them 100% compatible with Google Sheets and Microsoft Excel.\n\n"
                "Steps to Import into Google Sheets:\n"
                "------------------------------------\n"
                "1. Open your web browser and go to: https://sheets.new (creates a new Google Sheet)\n"
                "2. Click 'File' menu -> 'Import'.\n"
                "3. Select the 'Upload' tab and drag any of the exported CSV files into the window:\n"
                "   - 01_students.csv\n"
                "   - 02_semesters.csv\n"
                "   - 03_subject_marks.csv\n"
                "   - 04_seminars.csv\n"
                "   - 05_activities.csv\n"
                "   - 06_gap_drop_years.csv\n"
                "4. In the Import settings dialog:\n"
                "   - Import location: 'Insert new sheet(s)' or 'Replace current sheet'\n"
                "   - Separator type: 'Detect automatically' (or Comma)\n"
                "   - Convert text to numbers, dates, and formulas: YES\n"
                "5. Click 'Import data'.\n"
                "6. Repeat for each CSV if you want all tables in separate tabs of the same spreadsheet.\n"
            )
        results["files"]["import_guide"] = guide_path

        return results
