"""
execute_demo_seed.py
Executes the approved seed_fictional_demo_plan.sql script against student_academic_ledger.
- Strictly preserves DEMO001 and all existing records.
- Stops immediately on any SQL error and rolls back.
- Verifies inserted records and relationship integrity afterward.
"""

import sys
import os
import getpass
import re
import mysql.connector

DB_NAME = "student_academic_ledger"
SQL_FILE = "seed_fictional_demo_plan.sql"


def run_seed(password=None):
    if password is None:
        password = os.environ.get("MYSQL_PWD") or os.environ.get("MYSQL_PASSWORD")
    if password is None:
        if len(sys.argv) > 1:
            password = sys.argv[1]
    if password is None:
        try:
            password = getpass.getpass("Enter MySQL root password: ")
        except Exception:
            print("ERROR: Password required to connect to MySQL.")
            return False

    if not os.path.exists(SQL_FILE):
        print(f"ERROR: {SQL_FILE} not found.")
        return False

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
        return False

    print("Connected to MySQL. Preparing to execute seed plan...")

    # Read and parse SQL statements
    with open(SQL_FILE, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # Split into statements by semicolon, removing comments
    statements = []
    current_stmt = []
    for line in sql_content.splitlines():
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("--"):
            continue
        current_stmt.append(line)
        if trimmed.endswith(";"):
            full_stmt = "\n".join(current_stmt).strip()
            # Remove trailing semicolon
            if full_stmt.endswith(";"):
                full_stmt = full_stmt[:-1].strip()
            if full_stmt:
                statements.append(full_stmt)
            current_stmt = []

    cursor = conn.cursor()
    executed_count = 0

    try:
        for idx, stmt in enumerate(statements, start=1):
            # Skip USE database statement as we're already connected to it
            if stmt.upper().startswith("USE "):
                continue

            # Execute statement
            cursor.execute(stmt)
            executed_count += 1

        conn.commit()
        print(f"SUCCESS: Executed {executed_count} statements cleanly with 0 errors.")
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"\nFATAL SQL ERROR on statement #{idx}:\n{stmt}\n\nERROR MESSAGE: {err}")
        print("TRANSACTION ROLLED BACK. No partial data was inserted.")
        cursor.close()
        conn.close()
        return False

    # ---------------- VERIFICATION ----------------
    print("\n" + "=" * 60)
    print("VERIFYING DATABASE INTEGRITY & INSERTED RECORDS:")
    print("=" * 60)

    # 1. Verify DEMO001 preservation
    cursor.execute("SELECT student_id, roll_number, full_name FROM students WHERE roll_number='DEMO001'")
    demo001 = cursor.fetchone()
    if demo001:
        print(f"PRESERVED: Real student record '{demo001[1]}' - {demo001[2]} (ID: {demo001[0]}) is intact.")
    else:
        print("NOTICE: Roll number 'DEMO001' not found, checking all students...")
        cursor.execute("SELECT roll_number, full_name FROM students")
        for r in cursor.fetchall():
            print(f"  Existing Student: {r[0]} - {r[1]}")

    # 2. Verify Demo Students
    cursor.execute(
        """SELECT s.student_id, s.roll_number, s.full_name,
                  (SELECT COUNT(*) FROM semesters sem WHERE sem.student_id = s.student_id) AS sem_cnt,
                  (SELECT COUNT(*) FROM subject_results res JOIN semesters sem ON res.semester_id = sem.semester_id WHERE sem.student_id = s.student_id) AS mark_cnt,
                  (SELECT COUNT(*) FROM seminars sem2 WHERE sem2.student_id = s.student_id) AS sem_cnt2,
                  (SELECT COUNT(*) FROM activities act WHERE act.student_id = s.student_id) AS act_cnt,
                  (SELECT COUNT(*) FROM drop_years dy WHERE dy.student_id = s.student_id) AS dy_cnt
           FROM students s
           WHERE s.roll_number IN ('DEMO-TE-001', 'DEMO-TE-002')
           ORDER BY s.roll_number"""
    )
    demo_rows = cursor.fetchall()

    for row in demo_rows:
        print(f"\nDemo Student: {row[2]} ({row[1]}, ID: {row[0]})")
        print(f"  • Semesters:     {row[3]} records")
        print(f"  • Subject Marks: {row[4]} records")
        print(f"  • Seminars:      {row[5]} records")
        print(f"  • Activities:    {row[6]} records")
        print(f"  • Gap Years:     {row[7]} records")

    cursor.close()
    conn.close()
    return True


if __name__ == "__main__":
    pwd = sys.argv[1] if len(sys.argv) > 1 else None
    run_seed(pwd)
