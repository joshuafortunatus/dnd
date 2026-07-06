import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sheets_client import read_tab


class FakeValues:
    def __init__(self, values):
        self._values = values

    def get(self, spreadsheetId, range):  # noqa: A002 - matches googleapiclient's kwarg name
        self.requested_spreadsheet_id = spreadsheetId
        self.requested_range = range
        return self

    def execute(self):
        return {"values": self._values}


class FakeSpreadsheets:
    def __init__(self, values):
        self._values_resource = FakeValues(values)

    def values(self):
        return self._values_resource


class FakeService:
    def __init__(self, values):
        self._spreadsheets = FakeSpreadsheets(values)

    def spreadsheets(self):
        return self._spreadsheets


def test_read_tab_returns_rows_keyed_by_header():
    service = FakeService([["name", "content"], ["Hook", "Some text"]])

    assert read_tab(service, "sheet-1", "misc") == [{"name": "Hook", "content": "Some text"}]


def test_read_tab_pads_short_rows_with_empty_strings():
    service = FakeService([["type", "link", "name"], ["playable", "https://example.com"]])

    assert read_tab(service, "sheet-1", "characters") == [
        {"type": "playable", "link": "https://example.com", "name": ""}
    ]


def test_read_tab_empty_sheet_returns_empty_list():
    service = FakeService([])

    assert read_tab(service, "sheet-1", "misc") == []


def test_read_tab_requests_the_given_sheet_and_tab():
    service = FakeService([["name"], ["Hook"]])

    read_tab(service, "sheet-1", "misc")

    assert service._spreadsheets._values_resource.requested_spreadsheet_id == "sheet-1"
    assert service._spreadsheets._values_resource.requested_range == "misc"
