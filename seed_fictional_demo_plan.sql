-- ============================================================================
-- PROPOSED FICTIONAL DEMO DATA INSERTION PLAN
-- SAFE & IDEMPOTENT: PRESERVES DEMO001 AND ALL EXISTING REAL DATABASE RECORDS.
-- WILL NOT BE EXECUTED UNTIL YOU REVIEW AND APPROVE IT.
-- ============================================================================

USE student_academic_ledger;

-- PRESERVATION VERIFICATION:
-- Existing record 'DEMO001' and any existing rows in all tables are strictly preserved.
-- All demo students below use unique roll numbers prefixed with 'DEMO-' and names with '[DEMO]'.

-- ----------------------------------------------------------------------------
-- 1. INSERT SUBJECTS (Checks existence by name before inserting)
-- ----------------------------------------------------------------------------
INSERT INTO subjects (subject_name, subject_type)
SELECT * FROM (SELECT 'Database Management Systems' AS name, 'Theory' AS type) AS tmp
WHERE NOT EXISTS (SELECT 1 FROM subjects WHERE subject_name = 'Database Management Systems');

INSERT INTO subjects (subject_name, subject_type)
SELECT * FROM (SELECT 'DBMS Laboratory' AS name, 'Practical' AS type) AS tmp
WHERE NOT EXISTS (SELECT 1 FROM subjects WHERE subject_name = 'DBMS Laboratory');

INSERT INTO subjects (subject_name, subject_type)
SELECT * FROM (SELECT 'Computer Networks' AS name, 'Theory' AS type) AS tmp
WHERE NOT EXISTS (SELECT 1 FROM subjects WHERE subject_name = 'Computer Networks');

INSERT INTO subjects (subject_name, subject_type)
SELECT * FROM (SELECT 'Software Engineering' AS name, 'Theory' AS type) AS tmp
WHERE NOT EXISTS (SELECT 1 FROM subjects WHERE subject_name = 'Software Engineering');

INSERT INTO subjects (subject_name, subject_type)
SELECT * FROM (SELECT 'Data Structures & Algorithms' AS name, 'Theory' AS type) AS tmp
WHERE NOT EXISTS (SELECT 1 FROM subjects WHERE subject_name = 'Data Structures & Algorithms');

-- ----------------------------------------------------------------------------
-- 2. FICTIONAL DEMO STUDENT 1: [DEMO] Aarav Sharma (TE Regular, Eligible)
-- ----------------------------------------------------------------------------
INSERT INTO students (roll_number, full_name, date_of_birth, email, admission_year, tenth_percentage, twelfth_percentage, current_status)
SELECT 'DEMO-TE-001', '[DEMO] Aarav Sharma', '2004-04-15', 'aarav.demo@example.edu', 2022, 89.20, 86.50, 'Active'
WHERE NOT EXISTS (SELECT 1 FROM students WHERE roll_number = 'DEMO-TE-001');

SET @sid1 := (SELECT student_id FROM students WHERE roll_number = 'DEMO-TE-001');

-- Semesters 1 to 5 for Progression Graph demonstration
INSERT INTO semesters (student_id, semester_number, sgpa, cgpa)
SELECT @sid1, 1, 8.20, 8.20 WHERE NOT EXISTS (SELECT 1 FROM semesters WHERE student_id = @sid1 AND semester_number = 1);
INSERT INTO semesters (student_id, semester_number, sgpa, cgpa)
SELECT @sid1, 2, 8.45, 8.32 WHERE NOT EXISTS (SELECT 1 FROM semesters WHERE student_id = @sid1 AND semester_number = 2);
INSERT INTO semesters (student_id, semester_number, sgpa, cgpa)
SELECT @sid1, 3, 8.80, 8.48 WHERE NOT EXISTS (SELECT 1 FROM semesters WHERE student_id = @sid1 AND semester_number = 3);
INSERT INTO semesters (student_id, semester_number, sgpa, cgpa)
SELECT @sid1, 4, 8.65, 8.52 WHERE NOT EXISTS (SELECT 1 FROM semesters WHERE student_id = @sid1 AND semester_number = 4);
INSERT INTO semesters (student_id, semester_number, sgpa, cgpa)
SELECT @sid1, 5, 9.10, 8.64 WHERE NOT EXISTS (SELECT 1 FROM semesters WHERE student_id = @sid1 AND semester_number = 5);

SET @sem1_5 := (SELECT semester_id FROM semesters WHERE student_id = @sid1 AND semester_number = 5);
SET @sub_dbms := (SELECT subject_id FROM subjects WHERE subject_name = 'Database Management Systems');
SET @sub_dbms_lab := (SELECT subject_id FROM subjects WHERE subject_name = 'DBMS Laboratory');
SET @sub_cn := (SELECT subject_id FROM subjects WHERE subject_name = 'Computer Networks');
SET @sub_se := (SELECT subject_id FROM subjects WHERE subject_name = 'Software Engineering');

-- Marks for Semester 5
INSERT INTO subject_results (semester_id, subject_id, internal_marks, external_marks, lab_marks)
SELECT @sem1_5, @sub_dbms, 19, 68, NULL
WHERE NOT EXISTS (SELECT 1 FROM subject_results WHERE semester_id = @sem1_5 AND subject_id = @sub_dbms);

INSERT INTO subject_results (semester_id, subject_id, internal_marks, external_marks, lab_marks)
SELECT @sem1_5, @sub_dbms_lab, 23, NULL, 24
WHERE NOT EXISTS (SELECT 1 FROM subject_results WHERE semester_id = @sem1_5 AND subject_id = @sub_dbms_lab);

INSERT INTO subject_results (semester_id, subject_id, internal_marks, external_marks, lab_marks)
SELECT @sem1_5, @sub_cn, 17, 64, NULL
WHERE NOT EXISTS (SELECT 1 FROM subject_results WHERE semester_id = @sem1_5 AND subject_id = @sub_cn);

INSERT INTO subject_results (semester_id, subject_id, internal_marks, external_marks, lab_marks)
SELECT @sem1_5, @sub_se, 18, 70, NULL
WHERE NOT EXISTS (SELECT 1 FROM subject_results WHERE semester_id = @sem1_5 AND subject_id = @sub_se);

-- Seminars (Internal & External demonstration)
INSERT INTO seminars (student_id, seminar_name, seminar_type, event_date, certificate_reference)
SELECT @sid1, 'Microservices Architecture & Docker', 'Internal', '2024-03-10', 'CERT-INT-2024-01'
WHERE NOT EXISTS (SELECT 1 FROM seminars WHERE student_id = @sid1 AND seminar_name = 'Microservices Architecture & Docker');

INSERT INTO seminars (student_id, seminar_name, seminar_type, event_date, certificate_reference)
SELECT @sid1, 'National Cloud Summit IEEE', 'External', '2024-08-22', 'IEEE-EXT-9981'
WHERE NOT EXISTS (SELECT 1 FROM seminars WHERE student_id = @sid1 AND seminar_name = 'National Cloud Summit IEEE');

-- Activities (Technical & Co-curricular demonstration)
INSERT INTO activities (student_id, activity_name, category, activity_date, description)
SELECT @sid1, 'Smart India Hackathon 2024', 'Technical', '2024-02-15', 'Automated civic grievance portal'
WHERE NOT EXISTS (SELECT 1 FROM activities WHERE student_id = @sid1 AND activity_name = 'Smart India Hackathon 2024');

INSERT INTO activities (student_id, activity_name, category, activity_date, description)
SELECT @sid1, 'Annual Inter-College Debate', 'Co-curricular', '2023-11-05', 'Secured 2nd Prize on Ethics in AI'
WHERE NOT EXISTS (SELECT 1 FROM activities WHERE student_id = @sid1 AND activity_name = 'Annual Inter-College Debate');


-- ----------------------------------------------------------------------------
-- 3. FICTIONAL DEMO STUDENT 2: [DEMO] Priya Patel (TE Regular, Gap Year Demo)
-- ----------------------------------------------------------------------------
INSERT INTO students (roll_number, full_name, date_of_birth, email, admission_year, tenth_percentage, twelfth_percentage, current_status)
SELECT 'DEMO-TE-002', '[DEMO] Priya Patel', '2003-11-20', 'priya.demo@example.edu', 2021, 92.40, 90.10, 'Active'
WHERE NOT EXISTS (SELECT 1 FROM students WHERE roll_number = 'DEMO-TE-002');

SET @sid2 := (SELECT student_id FROM students WHERE roll_number = 'DEMO-TE-002');

INSERT INTO semesters (student_id, semester_number, sgpa, cgpa)
SELECT @sid2, 1, 8.00, 8.00 WHERE NOT EXISTS (SELECT 1 FROM semesters WHERE student_id = @sid2 AND semester_number = 1);
INSERT INTO semesters (student_id, semester_number, sgpa, cgpa)
SELECT @sid2, 2, 8.10, 8.05 WHERE NOT EXISTS (SELECT 1 FROM semesters WHERE student_id = @sid2 AND semester_number = 2);
INSERT INTO semesters (student_id, semester_number, sgpa, cgpa)
SELECT @sid2, 3, 8.50, 8.20 WHERE NOT EXISTS (SELECT 1 FROM semesters WHERE student_id = @sid2 AND semester_number = 3);
INSERT INTO semesters (student_id, semester_number, sgpa, cgpa)
SELECT @sid2, 4, 8.70, 8.32 WHERE NOT EXISTS (SELECT 1 FROM semesters WHERE student_id = @sid2 AND semester_number = 4);
INSERT INTO semesters (student_id, semester_number, sgpa, cgpa)
SELECT @sid2, 5, 8.90, 8.44 WHERE NOT EXISTS (SELECT 1 FROM semesters WHERE student_id = @sid2 AND semester_number = 5);

SET @sem2_5 := (SELECT semester_id FROM semesters WHERE student_id = @sid2 AND semester_number = 5);
INSERT INTO subject_results (semester_id, subject_id, internal_marks, external_marks, lab_marks)
SELECT @sem2_5, @sub_dbms, 18, 65, NULL
WHERE NOT EXISTS (SELECT 1 FROM subject_results WHERE semester_id = @sem2_5 AND subject_id = @sub_dbms);

INSERT INTO subject_results (semester_id, subject_id, internal_marks, external_marks, lab_marks)
SELECT @sem2_5, @sub_dbms_lab, 24, NULL, 25
WHERE NOT EXISTS (SELECT 1 FROM subject_results WHERE semester_id = @sem2_5 AND subject_id = @sub_dbms_lab);

-- Seminars
INSERT INTO seminars (student_id, seminar_name, seminar_type, event_date, certificate_reference)
SELECT @sid2, 'Quantum Computing Fundamentals', 'External', '2024-04-12', 'QC-EXT-2024'
WHERE NOT EXISTS (SELECT 1 FROM seminars WHERE student_id = @sid2 AND seminar_name = 'Quantum Computing Fundamentals');

-- Activities (Extra-curricular demonstration)
INSERT INTO activities (student_id, activity_name, category, activity_date, description)
SELECT @sid2, 'College Cultural Dance Troupe', 'Extra-curricular', '2024-01-26', 'Lead performer in Republic Day event'
WHERE NOT EXISTS (SELECT 1 FROM activities WHERE student_id = @sid2 AND activity_name = 'College Cultural Dance Troupe');

-- Gap / Drop Year demonstration
INSERT INTO drop_years (student_id, start_year, end_year, reason)
SELECT @sid2, 2022, 2023, 'Medical leave approved by academic council'
WHERE NOT EXISTS (SELECT 1 FROM drop_years WHERE student_id = @sid2 AND start_year = 2022);

-- ============================================================================
-- END OF PROPOSED DEMO PLAN
-- ============================================================================
