import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sync_drive import load_campaigns, load_state, save_state, slugify


def test_slugify_basic():
    assert slugify("Session 12: The Fall") == "session-12-the-fall"


def test_slugify_strips_leading_trailing_punctuation():
    assert slugify("--Untitled Doc--") == "untitled-doc"


def test_slugify_falls_back_to_untitled_when_nothing_left():
    assert slugify("###") == "untitled"


def test_save_state_then_load_state_roundtrip(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    monkeypatch.setattr("sync_drive.STATE_PATH", state_path)

    save_state({"file-1": "2026-01-01T00:00:00Z"})

    assert load_state() == {"file-1": "2026-01-01T00:00:00Z"}


def test_load_state_missing_file_returns_empty_dict(tmp_path, monkeypatch):
    monkeypatch.setattr("sync_drive.STATE_PATH", tmp_path / "missing.json")

    assert load_state() == {}


def test_load_campaigns_reads_list(tmp_path, monkeypatch):
    config_path = tmp_path / "campaigns.yaml"
    config_path.write_text(
        "campaigns:\n  - slug: thats-fair\n    drive_folder_id: \"abc123\"\n    sheet_id: \"def456\"\n"
    )
    monkeypatch.setattr("sync_drive.CAMPAIGNS_CONFIG_PATH", config_path)

    assert load_campaigns() == [{"slug": "thats-fair", "drive_folder_id": "abc123", "sheet_id": "def456"}]


def test_load_campaigns_empty_file_returns_empty_list(tmp_path, monkeypatch):
    config_path = tmp_path / "campaigns.yaml"
    config_path.write_text("")
    monkeypatch.setattr("sync_drive.CAMPAIGNS_CONFIG_PATH", config_path)

    assert load_campaigns() == []
