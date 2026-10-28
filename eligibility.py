"""
eligibility.py
Module for inspecting and checking eligibility for regular TE students
on the current attendance roll.
Inspects existing fields and reports what is missing without inventing arbitrary rules.
"""

from typing import Dict, Any, Tuple, List


class StudentEligibilityChecker:
    """
    Checks if a student meets the criteria:
    1. Regular student (not diploma DSE, repeater, or drop unless regularized).
    2. Enrolled in TE (Third Year, Semesters 5 or 6).
    3. Present on the current attendance roll.
    """

    REQUIRED_CRITERIA_FIELDS = [
        ("year_of_study", "Year of Study (e.g. 'TE')"),
        ("student_type", "Student Type (e.g. 'Regular')"),
        ("is_on_attendance_roll", "Attendance Roll Flag (e.g. 1/True or 'On Roll')")
    ]

    @classmethod
    def inspect_record_fields(cls, student_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inspects existing fields in a student dictionary and reports
        which eligibility fields are present and which are missing from the schema.
        """
        present = []
        missing = []

        for field_key, field_label in cls.REQUIRED_CRITERIA_FIELDS:
            if field_key in student_record and student_record[field_key] is not None:
                present.append((field_key, field_label, student_record[field_key]))
            else:
                missing.append((field_key, field_label))

        return {
            "has_all_fields": len(missing) == 0,
            "present_fields": present,
            "missing_fields": missing
        }

    @classmethod
    def check_te_regular_eligibility(cls, student_record: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Evaluates eligibility for regular TE students on the current attendance roll.
        
        Returns:
            (is_eligible: bool, message: str, details: dict)
        """
        inspection = cls.inspect_record_fields(student_record)
        
        # If the schema does not have the required columns, report missing fields accurately
        if not inspection["has_all_fields"]:
            missing_names = [label for _, label in inspection["missing_fields"]]
            return (
                False,
                f"Cannot determine eligibility: Missing database fields [{', '.join(missing_names)}].",
                {"status": "INSUFFICIENT_DATA", "inspection": inspection}
            )

        # 1. Year of study check: Must be TE
        yos = str(student_record.get("year_of_study", "")).strip().upper()
        if yos not in ("TE", "THIRD YEAR", "3", "3RD YEAR"):
            return (
                False,
                f"Ineligible: Student is in '{yos}', not TE (Third Year).",
                {"status": "NOT_TE", "year_of_study": yos}
            )

        # 2. Student Type check: Must be Regular
        st_type = str(student_record.get("student_type", "")).strip().capitalize()
        if st_type != "Regular":
            return (
                False,
                f"Ineligible: Student type is '{st_type}'. Only 'Regular' students are permitted.",
                {"status": "NOT_REGULAR", "student_type": st_type}
            )

        # 3. Attendance Roll check: Must be on roll (True, 1, 'Yes', 'On Roll')
        roll_flag = student_record.get("is_on_attendance_roll")
        is_on_roll = False
        if isinstance(roll_flag, bool):
            is_on_roll = roll_flag
        elif isinstance(roll_flag, (int, float)):
            is_on_roll = (roll_flag == 1)
        elif isinstance(roll_flag, str):
            is_on_roll = roll_flag.strip().lower() in ("1", "true", "yes", "on roll", "present")

        if not is_on_roll:
            return (
                False,
                "Ineligible: Student is not on the current attendance roll.",
                {"status": "NOT_ON_ROLL", "is_on_attendance_roll": roll_flag}
            )

        # All checks passed!
        return (
            True,
            "Eligible: Regular TE student active on the current attendance roll.",
            {"status": "ELIGIBLE"}
        )
