import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from campaign_config import load_campaigns, slugify


def test_slugify_basic():
    assert slugify("Session 12: The Fall") == "session-12-the-fall"


def test_slugify_strips_leading_trailing_punctuation():
    assert slugify("--Untitled Doc--") == "untitled-doc"


def test_slugify_falls_back_to_untitled_when_nothing_left():
    assert slugify("###") == "untitled"


def test_load_campaigns_reads_list(tmp_path, monkeypatch):
    config_path = tmp_path / "campaigns.yaml"
    config_path.write_text("campaigns:\n  - slug: thats-fair\n    sheet_id: \"def456\"\n")
    monkeypatch.setattr("campaign_config.CAMPAIGNS_CONFIG_PATH", config_path)

    assert load_campaigns() == [{"slug": "thats-fair", "sheet_id": "def456"}]


def test_load_campaigns_empty_file_returns_empty_list(tmp_path, monkeypatch):
    config_path = tmp_path / "campaigns.yaml"
    config_path.write_text("")
    monkeypatch.setattr("campaign_config.CAMPAIGNS_CONFIG_PATH", config_path)

    assert load_campaigns() == []
