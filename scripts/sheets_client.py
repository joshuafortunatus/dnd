"""Shared Google Sheets API v4 helpers used by sync_sheet.py and fetch_ddb_character.py.

Auth: expects a service-account JSON key in the GOOGLE_CREDENTIALS_JSON env var
— the same credential this repo already uses for Drive (scripts/sync_drive.py).
The service account just also needs to be shared as a Viewer on each
campaign's Google Sheet (see data/campaigns.yaml).
"""

from __future__ import annotations

import json
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def load_credentials() -> service_account.Credentials:
    raw = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if not raw:
        raise SystemExit("GOOGLE_CREDENTIALS_JSON is not set — cannot authenticate to Sheets.")
    info = json.loads(raw)
    return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)


def build_service():
    return build("sheets", "v4", credentials=load_credentials())


def read_tab(service, sheet_id: str, tab_name: str) -> list[dict]:
    """Read a whole tab and return each row as a dict keyed by its header row.
    Rows shorter than the header (trailing blank cells, which Sheets omits)
    are padded with "" so every dict has every column."""
    result = service.spreadsheets().values().get(spreadsheetId=sheet_id, range=tab_name).execute()
    values = result.get("values", [])
    if not values:
        return []
    headers, *rows = values
    return [dict(zip(headers, row + [""] * (len(headers) - len(row)))) for row in rows]
