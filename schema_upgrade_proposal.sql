-- ============================================================================
-- SCHEMA UPGRADE PROPOSAL FOR student_academic_ledger (3NF & TE ELIGIBILITY)
-- NON-DESTRUCTIVE: DOES NOT DROP TABLES OR DELETE EXISTING RECORDS.
-- ALL EXISTING WORKING FEATURES AND DATA ARE FULLY PRESERVED.
-- ============================================================================

USE student_academic_ledger;

-- 1. ENHANCE STUDENTS TABLE (Safe column additions with defaults)
-- Adds year of study, student type, and attendance roll status needed for Requirement 5.
ALTER TABLE students
    ADD COLUMN IF NOT EXISTS year_of_study VARCHAR(10) DEFAULT 'TE',
    ADD COLUMN IF NOT EXISTS student_type VARCHAR(30) DEFAULT 'Regular',
    ADD COLUMN IF NOT EXISTS is_on_attendance_roll TINYINT(1) DEFAULT 1,
    ADD COLUMN IF NOT EXISTS submission_status VARCHAR(20) DEFAULT 'Draft',
    ADD COLUMN IF NOT EXISTS diploma_percentage DECIMAL(5, 2) NULL;

-- 2. ENHANCE SUBJECTS TABLE (Add credits for mathematically sound SGPA calculation)
ALTER TABLE subjects
    ADD COLUMN IF NOT EXISTS credits INT DEFAULT 3;

-- 3. ENSURE UNIQUE CONSTRAINTS (Prevents duplicate records and maintains 3NF integrity)
-- Semester constraint: A student can only have one record per semester (1 to 8)
SET @exist_idx := (
    SELECT COUNT(*) FROM information_schema.statistics
    WHERE table_schema = 'student_academic_ledger'
      AND table_name = 'semesters'
      AND index_name = 'uq_student_semester'
);
SET @sql_idx := IF(@exist_idx = 0,
    'ALTER TABLE semesters ADD CONSTRAINT uq_student_semester UNIQUE (student_id, semester_number);',
    'SELECT "uq_student_semester already exists";'
);
PREPARE stmt FROM @sql_idx;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Subject results constraint: A student cannot have duplicate results for the same subject in one semester
SET @exist_res_idx := (
    SELECT COUNT(*) FROM information_schema.statistics
    WHERE table_schema = 'student_academic_ledger'
      AND table_name = 'subject_results'
      AND index_name = 'uq_semester_subject'
);
SET @sql_res_idx := IF(@exist_res_idx = 0,
    'ALTER TABLE subject_results ADD CONSTRAINT uq_semester_subject UNIQUE (semester_id, subject_id);',
    'SELECT "uq_semester_subject already exists";'
);
PREPARE stmt FROM @sql_res_idx;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ============================================================================
-- END OF PROPOSED MIGRATION
-- ============================================================================
