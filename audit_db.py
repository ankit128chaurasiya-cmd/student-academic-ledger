"""
audit_db.py
Standalone read-only database audit script for Student Academic & Activity Ledger.
Connects to MySQL, inspects existing tables, columns, row counts, and relationships,
and reports row counts for students, semesters, subjects, subject_results,
seminars, activities, and drop_years without making any modifications.
"""

import sys
import os
import json
import getpass
import mysql.connector

DB_NAME = "student_academic_ledger"


def run_audit(password=None):
    if password is None:
        password = os.environ.get("MYSQL_PWD") or os.environ.get("MYSQL_PASSWORD")
    if password is None:
        try:
            password = getpass.getpass("Enter MySQL root password: ")
        except Exception:
            print("ERROR: Password required to connect to MySQL.")
            return

    try:
        conn = mysql.connector.connect(
            host="localhost",
            port=3306,
            user="root",
            password=password,
            database=DB_NAME
        )
    except mysql.connector.Error as err:
        print(f"DATABASE CONNECTION ERROR: {err}")
        return

    cursor = conn.cursor()
    cursor.execute("SHOW TABLES")
    tables = [r[0] for r in cursor.fetchall()]

    audit = {
        "database": DB_NAME,
        "tables": {},
        "row_counts": {},
        "students_summary": []
    }

    print("=" * 60)
    print(f"DATABASE SCHEMA & ROW COUNTS AUDIT: {DB_NAME}")
    print("=" * 60)

    for tbl in tables:
        cursor.execute(f"DESCRIBE `{tbl}`")
        cols = [r[0] for r in cursor.fetchall()]
        cursor.execute(f"SELECT COUNT(*) FROM `{tbl}`")
        cnt = cursor.fetchone()[0]
        audit["tables"][tbl] = cols
        audit["row_counts"][tbl] = cnt
        print(f"Table '{tbl}': {cnt} row(s) | Columns: {', '.join(cols)}")

    print("\n" + "=" * 60)
    print("STUDENT-SPECIFIC LINKED RECORDS:")
    print("=" * 60)

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

        audit["students_summary"].append(s_info)
        print(f"Student: {name} (Roll: {roll}, ID: {sid})")
        print(f"  • Semesters:       {s_info['semesters']}")
        print(f"  • Subject Marks:   {s_info['marks']}")
        print(f"  • Seminars:        {s_info['seminars']}")
        print(f"  • Activities:      {s_info['activities']}")
        print(f"  • Gap/Drop Years:  {s_info['drop_years']}")

    cursor.close()
    conn.close()

    with open("db_schema_audit.json", "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=4)
    print("\nFull audit saved to db_schema_audit.json")


if __name__ == "__main__":
    pwd = sys.argv[1] if len(sys.argv) > 1 else None
    run_audit(pwd)
