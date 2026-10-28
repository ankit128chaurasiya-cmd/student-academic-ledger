"""
google_sheets_sync.py
Module for Google Sheets one-way synchronization.
Supports one-way push of validated student ledger data to Google Sheets tabs.
Safely checks configuration and prevents external uploads until user provides
credentials and explicit approval.
"""

import os
import json
from typing import Dict, Any, List, Tuple, Optional
from csv_export import sanitize_for_spreadsheet, format_mark, format_date


class GoogleSheetsSyncService:
    """
    Manages one-way sync from Student Academic & Activity Ledger to Google Sheets.
    Safe-by-default: Never attempts external network calls unless explicitly configured.
    """

    CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "google_sheets_config.json")

    def __init__(self, config_path: str = CONFIG_FILE):
        self.config_path = config_path

    def load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_config(self, spreadsheet_id: str, credentials_path: str, enabled: bool = False):
        config = {
            "spreadsheet_id": spreadsheet_id.strip(),
            "credentials_path": credentials_path.strip(),
            "enabled": enabled
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)

    def resolve_credentials_path(self, creds_path: Optional[str] = None) -> Optional[str]:
        """
        Resolves the credentials file path.
        If the given path exists, returns its absolute path.
        Otherwise falls back to looking for the filename in the config directory or current working directory.
        """
        if not creds_path:
            config = self.load_config()
            creds_path = config.get("credentials_path", "")

        if not creds_path:
            return None

        # 1. Direct path check
        if os.path.exists(creds_path):
            return os.path.abspath(creds_path)

        # 2. Check in directory of config_path
        filename = os.path.basename(creds_path)
        config_dir = os.path.dirname(os.path.abspath(self.config_path))
        candidate_config_dir = os.path.join(config_dir, filename)
        if os.path.exists(candidate_config_dir):
            return candidate_config_dir

        # 3. Check in current working directory
        candidate_cwd = os.path.join(os.getcwd(), filename)
        if os.path.exists(candidate_cwd):
            return candidate_cwd

        return None

    def get_service_account_email(self, creds_path: Optional[str] = None) -> Optional[str]:
        """
        Extracts the service account client_email safely without exposing private keys.
        """
        env_creds = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if env_creds:
            try:
                data = json.loads(env_creds)
                return data.get("client_email")
            except Exception:
                pass

        resolved_path = self.resolve_credentials_path(creds_path)
        if not resolved_path:
            return None
        try:
            with open(resolved_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("client_email")
        except Exception:
            return None

    def is_configured(self) -> Tuple[bool, str]:
        """
        Returns (is_ready, status_message).
        Safe check without initiating network requests.
        """
        # 1. Environment variable support for cloud/Render deployments
        env_sid = os.environ.get("SPREADSHEET_ID")
        env_creds = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if env_sid and env_creds:
            email = self.get_service_account_email()
            email_str = f" ({email})" if email else ""
            return (True, f"Ready for sync (Cloud Environment credentials detected{email_str}).")

        config = self.load_config()
        if not config:
            return (
                False,
                "Google Sheets sync is not configured. Please use the CSV Export fallback "
                "or configure credentials when ready."
            )

        if not config.get("enabled"):
            return (
                False,
                "Google Sheets sync is currently disabled. Enable it in settings when approved."
            )

        spreadsheet_id = os.environ.get("SPREADSHEET_ID") or config.get("spreadsheet_id")
        creds_path = config.get("credentials_path")

        if not spreadsheet_id:
            return (False, "Missing Google Spreadsheet ID in configuration.")

        resolved = self.resolve_credentials_path(creds_path)
        if not resolved and not env_creds:
            return (False, f"Credentials file not found at: {creds_path}")

        email = self.get_service_account_email(resolved)
        email_str = f" ({email})" if email else ""

        return (True, f"Ready for sync (Service Account credentials detected{email_str}).")

    def format_error_message(self, exc: Exception, spreadsheet_id: str, client_email: str = "") -> str:
        """
        Constructs an explicit, human-readable, and actionable error message
        from an exception encountered during Google Sheets operations.
        Never returns a blank or generic failure message.
        """
        exc_str = str(exc).strip()
        exc_type = type(exc).__name__

        # Check underlying causes if chained (e.g. PermissionError from APIError)
        cause = getattr(exc, "__cause__", None)
        cause_str = str(cause).strip() if cause else ""
        cause_type = type(cause).__name__ if cause else ""

        full_details = f"{exc_type}: {exc_str}" if exc_str else exc_type
        if cause_str:
            full_details += f" (Caused by {cause_type}: {cause_str})"

        # Check if HTTP 403 / Permission Denied
        is_403 = False
        if isinstance(exc, PermissionError) or "403" in exc_str or "permission" in exc_str.lower():
            is_403 = True
        elif cause and ("403" in cause_str or "permission" in cause_str.lower()):
            is_403 = True
        elif hasattr(exc, "response") and getattr(exc.response, "status_code", None) == 403:
            is_403 = True
        elif cause and hasattr(cause, "response") and getattr(cause.response, "status_code", None) == 403:
            is_403 = True

        if is_403:
            email_display = client_email or self.get_service_account_email() or "your service account email"
            return (
                "Google Sheets sync failed: Permission Denied (HTTP 403).\n\n"
                "The Google Spreadsheet has not been shared with your Service Account.\n\n"
                f"- Spreadsheet ID: {spreadsheet_id}\n"
                f"- Service Account Email: {email_display}\n\n"
                "Action Required to Resolve:\n"
                "1. Open your spreadsheet in Google Sheets:\n"
                f"   https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit\n"
                "2. Click the 'Share' button in the top right.\n"
                f"3. In the 'Add people and groups' field, paste:\n"
                f"   {email_display}\n"
                "4. Select 'Editor' role and uncheck 'Notify people' (service accounts do not have inboxes).\n"
                "5. Click 'Share' / 'Done', then retry the synchronization."
            )

        # Check if HTTP 404 / Spreadsheet Not Found
        is_404 = False
        if "SpreadsheetNotFound" in exc_type or "404" in exc_str or "not found" in exc_str.lower():
            is_404 = True
        elif cause and ("SpreadsheetNotFound" in cause_type or "404" in cause_str or "not found" in cause_str.lower()):
            is_404 = True
        elif hasattr(exc, "response") and getattr(exc.response, "status_code", None) == 404:
            is_404 = True

        if is_404:
            return (
                "Google Sheets sync failed: Spreadsheet Not Found (HTTP 404).\n\n"
                f"- Spreadsheet ID: {spreadsheet_id}\n\n"
                "Please verify that the Spreadsheet ID in google_sheets_config.json is correct and that "
                "the spreadsheet has not been deleted."
            )

        # Check for Google Drive API disabled in Google Cloud Project
        if "Google Drive API" in exc_str or "drive.googleapis.com" in exc_str or (cause and ("Google Drive API" in cause_str or "drive.googleapis.com" in cause_str)):
            return (
                "Google Sheets sync failed: Google Drive API is disabled in your Google Cloud Project.\n\n"
                "Please enable the Google Drive API in the Google Cloud Console for your project:\n"
                "https://console.developers.google.com/apis/api/drive.googleapis.com/overview\n\n"
                f"Details: {full_details}"
            )

        # Check for Network connection issues
        if "ConnectionError" in exc_type or "Timeout" in exc_type or "URLError" in exc_type:
            return (
                "Google Sheets sync failed: Network connection error.\n\n"
                "Unable to connect to Google APIs. Please check your internet connection and proxy settings.\n\n"
                f"Details: {full_details}"
            )

        # General failure with full readable detail
        return (
            f"Google Sheets sync failed: {full_details}\n\n"
            f"- Spreadsheet ID: {spreadsheet_id}\n"
            f"- Credentials file: {self.resolve_credentials_path() or 'Not found'}\n"
            "If the problem persists, please check your network connection and Google Cloud project API permissions."
        )

    def test_connection(self) -> Tuple[bool, str]:
        """
        Safely tests Google Sheets API connection and authorization to the configured
        spreadsheet without modifying any data.
        Returns (success: bool, message: str).
        """
        ready, msg = self.is_configured()
        if not ready:
            return (False, msg)

        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError:
            return (
                False,
                "Google Sheets libraries (gspread, google-auth) are not installed.\n"
                "Run: py -m pip install gspread google-auth"
            )

        config = self.load_config()
        spreadsheet_id = os.environ.get("SPREADSHEET_ID") or config.get("spreadsheet_id", "").strip()
        env_creds = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if env_creds:
            client_email = self.get_service_account_email() or ""
            creds_path = None
        else:
            creds_path = self.resolve_credentials_path(config.get("credentials_path", ""))
            client_email = self.get_service_account_email(creds_path) or ""

        try:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            if env_creds:
                creds = Credentials.from_service_account_info(json.loads(env_creds), scopes=scopes)
            else:
                creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key(spreadsheet_id)

            worksheets = [w.title for w in spreadsheet.worksheets()]
            sheet_title = getattr(spreadsheet, "title", "Untitled")

            return (
                True,
                f"Connection Successful!\n\n"
                f"- Spreadsheet: \"{sheet_title}\"\n"
                f"- Spreadsheet ID: {spreadsheet_id}\n"
                f"- Existing Worksheets ({len(worksheets)}): {', '.join(worksheets)}\n"
                f"- Authenticated As: {creds.service_account_email}\n\n"
                f"The service account has valid access to read and update this spreadsheet."
            )
        except Exception as exc:
            return (False, self.format_error_message(exc, spreadsheet_id, client_email))

    def prepare_sheets_payload(self, db_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[List[Any]]]:
        """
        Converts the normalized database dictionary into safe, 2D tabular rows
        for Google Sheets worksheets, protected against formula injection.
        """
        payload = {}

        # 1. Students Sheet
        st_headers = [
            "Roll Number", "Full Name", "Date of Birth", "Email",
            "Admission Year", "10th Percentage", "12th Percentage",
            "Current Status", "Year of Study", "Student Type", "Attendance Roll Status"
        ]
        st_rows = [st_headers]
        for s in db_data.get("students", []):
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
                sanitize_for_spreadsheet(s.get("roll_number", "")),
                sanitize_for_spreadsheet(s.get("full_name", "")),
                format_date(s.get("date_of_birth")),
                sanitize_for_spreadsheet(s.get("email", "")),
                sanitize_for_spreadsheet(s.get("admission_year", "")),
                format_mark(s.get("tenth_percentage")),
                format_mark(s.get("twelfth_percentage")),
                sanitize_for_spreadsheet(s.get("current_status", "Active")),
                sanitize_for_spreadsheet(s.get("year_of_study", "")),
                sanitize_for_spreadsheet(s.get("student_type", "Regular")),
                sanitize_for_spreadsheet(roll_status or "")
            ])
        payload["Students"] = st_rows

        # 2. Semesters Sheet
        sem_headers = ["Roll Number", "Student Name", "Semester Number", "SGPA", "CGPA"]
        sem_rows = [sem_headers]
        for sem in db_data.get("semesters", []):
            sem_rows.append([
                sanitize_for_spreadsheet(sem.get("roll_number", "")),
                sanitize_for_spreadsheet(sem.get("full_name", "")),
                sanitize_for_spreadsheet(sem.get("semester_number", "")),
                format_mark(sem.get("sgpa")),
                format_mark(sem.get("cgpa"))
            ])
        payload["Semesters"] = sem_rows

        # 3. Subject Marks Sheet
        marks_headers = [
            "Roll Number", "Student Name", "Semester", "Subject Name",
            "Subject Type", "Internal Marks", "External Marks", "Lab Marks"
        ]
        marks_rows = [marks_headers]
        for m in db_data.get("marks", []):
            marks_rows.append([
                sanitize_for_spreadsheet(m.get("roll_number", "")),
                sanitize_for_spreadsheet(m.get("full_name", "")),
                sanitize_for_spreadsheet(m.get("semester_number", "")),
                sanitize_for_spreadsheet(m.get("subject_name", "")),
                sanitize_for_spreadsheet(m.get("subject_type", "")),
                format_mark(m.get("internal_marks")),
                format_mark(m.get("external_marks")),
                format_mark(m.get("lab_marks"))
            ])
        payload["Subject_Marks"] = marks_rows

        # 4. Seminars Sheet
        sem_headers = [
            "Roll Number", "Student Name", "Seminar Name",
            "Seminar Type", "Event Date", "Certificate Reference"
        ]
        sem_rows = [sem_headers]
        for sm in db_data.get("seminars", []):
            sem_rows.append([
                sanitize_for_spreadsheet(sm.get("roll_number", "")),
                sanitize_for_spreadsheet(sm.get("full_name", "")),
                sanitize_for_spreadsheet(sm.get("seminar_name", "")),
                sanitize_for_spreadsheet(sm.get("seminar_type", "")),
                format_date(sm.get("event_date")),
                sanitize_for_spreadsheet(sm.get("certificate_reference", ""))
            ])
        payload["Seminars"] = sem_rows

        # 5. Activities Sheet
        act_headers = [
            "Roll Number", "Student Name", "Activity Name",
            "Category", "Activity Date", "Description"
        ]
        act_rows = [act_headers]
        for a in db_data.get("activities", []):
            act_rows.append([
                sanitize_for_spreadsheet(a.get("roll_number", "")),
                sanitize_for_spreadsheet(a.get("full_name", "")),
                sanitize_for_spreadsheet(a.get("activity_name", "")),
                sanitize_for_spreadsheet(a.get("category", "")),
                format_date(a.get("activity_date")),
                sanitize_for_spreadsheet(a.get("description", ""))
            ])
        payload["Activities"] = act_rows

        # 6. Drop Years Sheet
        drop_headers = ["Roll Number", "Student Name", "Start Year", "End Year", "Reason"]
        drop_rows = [drop_headers]
        for d in db_data.get("drop_years", []):
            drop_rows.append([
                sanitize_for_spreadsheet(d.get("roll_number", "")),
                sanitize_for_spreadsheet(d.get("full_name", "")),
                sanitize_for_spreadsheet(d.get("start_year", "")),
                sanitize_for_spreadsheet(d.get("end_year", "")),
                sanitize_for_spreadsheet(d.get("reason", ""))
            ])
        payload["Gap_Drop_Years"] = drop_rows

        return payload

    def push_to_google_sheets(self, db_data: Dict[str, List[Dict[str, Any]]]) -> Tuple[bool, str]:
        """
        Performs one-way push to Google Sheets.
        If gspread is installed and configured, performs the upload.
        Otherwise safely informs the user with explicit error information.
        """
        ready, msg = self.is_configured()
        if not ready:
            return (False, msg)

        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError:
            return (
                False,
                "Google Sheets libraries (gspread, google-auth) are not installed.\n"
                "You can install them via: py -m pip install gspread google-auth\n"
                "In the meantime, the validated CSV export provides full Google Sheets compatibility."
            )

        config = self.load_config()
        spreadsheet_id = os.environ.get("SPREADSHEET_ID") or config.get("spreadsheet_id", "").strip()
        env_creds = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if env_creds:
            client_email = self.get_service_account_email() or ""
            creds_path = None
        else:
            creds_path = self.resolve_credentials_path(config.get("credentials_path", ""))
            client_email = self.get_service_account_email(creds_path) or ""

        try:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            if env_creds:
                creds = Credentials.from_service_account_info(json.loads(env_creds), scopes=scopes)
            else:
                creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key(spreadsheet_id)

            payload = self.prepare_sheets_payload(db_data)

            for tab_name, rows in payload.items():
                max_cols = max(len(r) for r in rows) if rows else 15
                needed_rows = max(len(rows) + 20, 50)
                needed_cols = max(max_cols, 15)

                try:
                    worksheet = spreadsheet.worksheet(tab_name)
                    # Resize if existing sheet has fewer rows or columns
                    if getattr(worksheet, "row_count", 0) < needed_rows or getattr(worksheet, "col_count", 0) < needed_cols:
                        new_r = max(getattr(worksheet, "row_count", 0), needed_rows)
                        new_c = max(getattr(worksheet, "col_count", 0), needed_cols)
                        try:
                            worksheet.resize(rows=new_r, cols=new_c)
                        except Exception:
                            pass
                    worksheet.clear()
                except gspread.WorksheetNotFound:
                    worksheet = spreadsheet.add_worksheet(title=tab_name, rows=needed_rows, cols=needed_cols)

                # In gspread 6.x, values is the first positional parameter (or values=rows keyword)
                worksheet.update(values=rows)

            sheet_title = getattr(spreadsheet, "title", "Spreadsheet")
            return (
                True,
                f"Successfully synchronized {len(payload)} sheets to Google Spreadsheet "
                f"\"{sheet_title}\" ({spreadsheet_id})."
            )

        except Exception as e:
            return (False, self.format_error_message(e, spreadsheet_id, client_email))
