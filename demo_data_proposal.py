"""
demo_data_proposal.py
Prepares clearly labelled fictional demo students and records.
Demonstrates multiple students across years, DSE, gap years, seminars, and activities
without conflicting with real student records.
All demo students are prefixed with [DEMO] and have roll numbers starting with DEMO-.
"""

from typing import List, Dict, Any


DEMO_STUDENTS: List[Dict[str, Any]] = [
    {
        "roll_number": "DEMO-TE-001",
        "full_name": "[DEMO] Aarav Sharma",
        "date_of_birth": "2004-04-15",
        "email": "aarav.demo@example.edu",
        "admission_year": 2022,
        "tenth_percentage": 89.2,
        "twelfth_percentage": 86.5,
        "current_status": "Active",
        "year_of_study": "TE",
        "student_type": "Regular",
        "is_on_attendance_roll": 1,
        "semesters": [
            {"semester_number": 1, "sgpa": 8.20, "cgpa": 8.20},
            {"semester_number": 2, "sgpa": 8.45, "cgpa": 8.32},
            {"semester_number": 3, "sgpa": 8.80, "cgpa": 8.48},
            {"semester_number": 4, "sgpa": 8.65, "cgpa": 8.52},
            {"semester_number": 5, "sgpa": 9.10, "cgpa": 8.64}
        ],
        "marks": [
            {"semester_number": 5, "subject_name": "Database Management Systems", "subject_type": "Theory", "internal_marks": 19, "external_marks": 68, "lab_marks": None},
            {"semester_number": 5, "subject_name": "DBMS Laboratory", "subject_type": "Practical", "internal_marks": 23, "external_marks": None, "lab_marks": 24},
            {"semester_number": 5, "subject_name": "Computer Networks", "subject_type": "Theory", "internal_marks": 17, "external_marks": 64, "lab_marks": None},
            {"semester_number": 5, "subject_name": "Software Engineering", "subject_type": "Theory", "internal_marks": 18, "external_marks": 70, "lab_marks": None}
        ],
        "seminars": [
            {"seminar_name": "Microservices Architecture & Docker", "seminar_type": "Internal", "event_date": "2024-03-10", "certificate_reference": "CERT-INT-2024-01"},
            {"seminar_name": "National Cloud Summit IEEE", "seminar_type": "External", "event_date": "2024-08-22", "certificate_reference": "IEEE-EXT-9981"}
        ],
        "activities": [
            {"activity_name": "Smart India Hackathon 2024", "category": "Technical", "activity_date": "2024-02-15", "description": "Developed automated civic grievance redressal portal"},
            {"activity_name": "Annual Inter-College Debate", "category": "Co-curricular", "activity_date": "2023-11-05", "description": "Secured 2nd Prize on Ethics in AI"}
        ],
        "drop_years": []
    },
    {
        "roll_number": "DEMO-TE-002",
        "full_name": "[DEMO] Priya Patel",
        "date_of_birth": "2003-11-20",
        "email": "priya.demo@example.edu",
        "admission_year": 2021,
        "tenth_percentage": 92.4,
        "twelfth_percentage": 90.1,
        "current_status": "Active",
        "year_of_study": "TE",
        "student_type": "Regular",
        "is_on_attendance_roll": 1,
        "semesters": [
            {"semester_number": 1, "sgpa": 8.00, "cgpa": 8.00},
            {"semester_number": 2, "sgpa": 8.10, "cgpa": 8.05},
            {"semester_number": 3, "sgpa": 8.50, "cgpa": 8.20},
            {"semester_number": 4, "sgpa": 8.70, "cgpa": 8.32},
            {"semester_number": 5, "sgpa": 8.90, "cgpa": 8.44}
        ],
        "marks": [
            {"semester_number": 5, "subject_name": "Database Management Systems", "subject_type": "Theory", "internal_marks": 18, "external_marks": 65, "lab_marks": None},
            {"semester_number": 5, "subject_name": "DBMS Laboratory", "subject_type": "Practical", "internal_marks": 24, "external_marks": None, "lab_marks": 25},
            {"semester_number": 5, "subject_name": "Operating Systems", "subject_type": "Theory", "internal_marks": 19, "external_marks": 69, "lab_marks": None}
        ],
        "seminars": [
            {"seminar_name": "Quantum Computing Fundamentals", "seminar_type": "External", "event_date": "2024-04-12", "certificate_reference": "QC-EXT-2024"}
        ],
        "activities": [
            {"activity_name": "College Cultural Dance Troupe", "category": "Extra-curricular", "activity_date": "2024-01-26", "description": "Lead performer in Republic Day event"},
            {"activity_name": "ACM Coding Contest", "category": "Technical", "activity_date": "2023-10-18", "description": "Top 10 Finalist"}
        ],
        "drop_years": [
            {"start_year": 2022, "end_year": 2023, "reason": "Medical leave approved by academic council"}
        ]
    },
    {
        "roll_number": "DEMO-DSE-003",
        "full_name": "[DEMO] Sneha Deshmukh",
        "date_of_birth": "2003-08-05",
        "email": "sneha.demo@example.edu",
        "admission_year": 2023,
        "tenth_percentage": 88.0,
        "twelfth_percentage": None,  # Diploma student
        "current_status": "Active",
        "year_of_study": "TE",
        "student_type": "Direct Second Year",
        "is_on_attendance_roll": 1,
        "semesters": [
            {"semester_number": 3, "sgpa": 8.60, "cgpa": 8.60},
            {"semester_number": 4, "sgpa": 8.75, "cgpa": 8.67},
            {"semester_number": 5, "sgpa": 8.95, "cgpa": 8.76}
        ],
        "marks": [
            {"semester_number": 5, "subject_name": "Database Management Systems", "subject_type": "Theory", "internal_marks": 20, "external_marks": 70, "lab_marks": None}
        ],
        "seminars": [
            {"seminar_name": "Cybersecurity Threats & Defenses", "seminar_type": "Internal", "event_date": "2024-02-28", "certificate_reference": "CYBER-INT-404"}
        ],
        "activities": [
            {"activity_name": "Robotics Club Lead", "category": "Technical", "activity_date": "2024-03-02", "description": "Designed line-follower robot"}
        ],
        "drop_years": []
    },
    {
        "roll_number": "DEMO-SE-004",
        "full_name": "[DEMO] Rohan Kulkarni",
        "date_of_birth": "2005-02-14",
        "email": "rohan.demo@example.edu",
        "admission_year": 2023,
        "tenth_percentage": 85.5,
        "twelfth_percentage": 82.0,
        "current_status": "Active",
        "year_of_study": "SE",
        "student_type": "Regular",
        "is_on_attendance_roll": 1,
        "semesters": [
            {"semester_number": 1, "sgpa": 7.80, "cgpa": 7.80},
            {"semester_number": 2, "sgpa": 8.10, "cgpa": 7.95},
            {"semester_number": 3, "sgpa": 8.30, "cgpa": 8.07}
        ],
        "marks": [
            {"semester_number": 3, "subject_name": "Data Structures & Algorithms", "subject_type": "Theory", "internal_marks": 17, "external_marks": 61, "lab_marks": None}
        ],
        "seminars": [
            {"seminar_name": "Introduction to Web Development", "seminar_type": "Internal", "event_date": "2023-09-14", "certificate_reference": "WEB-INT-101"}
        ],
        "activities": [
            {"activity_name": "Blood Donation Camp Volunteer", "category": "Extra-curricular", "activity_date": "2023-12-01", "description": "Organized donor registration"}
        ],
        "drop_years": []
    }
]


def print_demo_summary():
    print(f"Total Demo Students defined: {len(DEMO_STUDENTS)}")
    for s in DEMO_STUDENTS:
        print(f"- {s['roll_number']} | {s['full_name']} | Year: {s['year_of_study']} | Type: {s['student_type']} | On Roll: {s['is_on_attendance_roll']}")


if __name__ == "__main__":
    print_demo_summary()
