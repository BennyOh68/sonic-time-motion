"""
Google Sheets export helper for Time & Motion Study.

Provides append-only export to Google Sheets using a service account.
All user data lives in ONE pre-shared spreadsheet, each user in their
own worksheet tab named: {username}_time_motion

Usage:
    from google_sheets_helper import GoogleSheetsExporter

    exporter = GoogleSheetsExporter(
        spreadsheet_id="1ABC...xyz",
        credentials_dict=st.secrets["gcp_service_account"],
    )

    sheet_url = exporter.append_user_data("john", dataframe)
"""

import json
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from typing import Optional, Dict

# Sheets-only scope — no Drive API required.
# The spreadsheet must be pre-created and shared with the service account.
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]


class GoogleSheetsExporter:
    """Handles Google Sheets authentication and append-only data export."""

    def __init__(
        self,
        spreadsheet_id: str,
        credentials_dict: Optional[Dict] = None,
        credentials_path: Optional[str] = None,
    ):
        """
        Initialize with a pre-existing spreadsheet ID and service account
        credentials.

        The target spreadsheet must already exist and be shared (Editor)
        with the service account's email address.  No Google Drive API
        calls are made — only the Sheets API is used.

        Args:
            spreadsheet_id:  The Google Sheets spreadsheet ID (from the URL)
            credentials_dict: Dict of service account key fields
                              (from st.secrets or env var JSON)
            credentials_path: Path to a service account JSON key file

        Raises:
            ValueError: If neither credentials source is provided
        """
        self.spreadsheet_id = spreadsheet_id

        if credentials_dict:
            # Fix: Streamlit TOML secrets may store private_key with
            # escaped \\n literals instead of actual newline characters,
            # which causes a PEM decode error ("Unable to load PEM file").
            # Convert literal "\\n" → real "\n" so the cryptography
            # library can parse the private key correctly.
            # Also, deep-copy via JSON round-trip — st.secrets is read-only
            # and even dict() does not fully detach from it.
            credentials_dict = json.loads(json.dumps(dict(credentials_dict)))
            if "private_key" in credentials_dict:
                credentials_dict["private_key"] = (
                    credentials_dict["private_key"].replace("\\n", "\n")
                )
            self.creds = Credentials.from_service_account_info(
                credentials_dict, scopes=SCOPES
            )
        elif credentials_path:
            self.creds = Credentials.from_service_account_file(
                credentials_path, scopes=SCOPES
            )
        else:
            raise ValueError(
                "Must provide either credentials_dict or credentials_path"
            )

        self.client = gspread.authorize(self.creds)

    def append_user_data(self, username: str, df: pd.DataFrame) -> str:
        """
        Append DataFrame rows to a per-user worksheet TAB within the
        master spreadsheet.

        - Worksheet tab name: {username}_time_motion
        - Creates the worksheet tab if it doesn't exist (with headers)
        - Appends only new rows if the tab already has data (no duplicate
          headers)
        - Data is NEVER overwritten — this is append-only

        Args:
            username:  Current logged-in username
            df:        DataFrame whose rows will be appended

        Returns:
            The Google Sheets URL of the target spreadsheet
        """
        tab_name = f"{username}_time_motion"
        spreadsheet = self.client.open_by_key(self.spreadsheet_id)

        try:
            worksheet = spreadsheet.worksheet(tab_name)
            # Tab exists → append rows without re-writing headers
            existing_data = worksheet.get_all_values()
            if not existing_data:
                worksheet.update(
                    [df.columns.values.tolist()] + df.values.tolist()
                )
            else:
                worksheet.append_rows(df.values.tolist())

        except gspread.WorksheetNotFound:
            # First time for this user → create tab with headers + data
            worksheet = spreadsheet.add_worksheet(
                title=tab_name,
                rows=str(max(2, len(df) + 1)),
                cols=str(len(df.columns)),
            )
            worksheet.update(
                [df.columns.values.tolist()] + df.values.tolist()
            )

        return f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}"
