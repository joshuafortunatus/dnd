import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sync_sheet import (
    markdown_table,
    parse_sheet_date,
    sync_characters,
    sync_lore,
    sync_locations,
    sync_misc,
    sync_quests,
    sync_sessions,
    sync_skills,
    write_page,
)


def test_markdown_table_basic():
    table = markdown_table(["Name", "Type"], [["Phandalin", "Town"]])

    assert table == "| Name | Type |\n| :---- | :---- |\n| Phandalin | Town |\n"


def test_markdown_table_converts_newlines_to_br_so_the_row_cant_break():
    table = markdown_table(["Summary"], [["Line one\nLine two"]])

    assert "Line one<br>Line two" in table
    assert "\n" not in table.split("\n")[2]  # the data row itself has no literal newline


def test_markdown_table_escapes_pipes():
    table = markdown_table(["Summary"], [["a | b"]])

    assert "a \\| b" in table


def test_parse_sheet_date_two_digit_year():
    assert parse_sheet_date("6/27/26") == "2026-06-27"


def test_parse_sheet_date_pads_single_digit_month_and_day():
    assert parse_sheet_date("8/16/25") == "2025-08-16"


def test_parse_sheet_date_blank_returns_none():
    assert parse_sheet_date("  ") is None


def test_parse_sheet_date_unparseable_returns_none():
    assert parse_sheet_date("not a date") is None


def test_sync_sessions_groups_events_by_session_number(tmp_path, monkeypatch):
    monkeypatch.setattr("sync_sheet.CAMPAIGNS_DIR", tmp_path)
    rows = [
        {"session_number": "1", "date": "8/16/25", "events": "First event"},
        {"session_number": "1", "date": "8/16/25", "events": "Second event"},
        {"session_number": "2", "date": "8/23/25", "events": "Third event"},
    ]

    count = sync_sessions(rows, "thats-fair")

    assert count == 2
    session_1 = (tmp_path / "thats-fair" / "sessions" / "session-01.md").read_text()
    assert "title: Session 1" in session_1
    assert "date: '2025-08-16'" in session_1
    assert "- First event" in session_1
    assert "- Second event" in session_1
    assert (tmp_path / "thats-fair" / "sessions" / "session-02.md").exists()


def test_sync_sessions_skips_rows_without_a_session_number(tmp_path, monkeypatch):
    monkeypatch.setattr("sync_sheet.CAMPAIGNS_DIR", tmp_path)
    rows = [{"session_number": "", "date": "", "events": "Orphan event"}]

    assert sync_sessions(rows, "thats-fair") == 0


def test_sync_quests_marks_completed_rows_with_a_checkmark(tmp_path, monkeypatch):
    monkeypatch.setattr("sync_sheet.CAMPAIGNS_DIR", tmp_path)
    rows = [
        {"quest": "Deliver supplies", "beneficiary": "Group", "is_completed": "yes"},
        {"quest": "Find the spy", "beneficiary": "Group", "is_completed": "no"},
    ]

    count = sync_quests(rows, "thats-fair")

    text = (tmp_path / "thats-fair" / "quests" / "quest-log.md").read_text()
    assert count == 1
    assert "| Deliver supplies | Group | ✔ |" in text
    assert "| Find the spy | Group |  |" in text


def test_sync_quests_no_rows_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr("sync_sheet.CAMPAIGNS_DIR", tmp_path)

    assert sync_quests([], "thats-fair") == 0
    assert not (tmp_path / "thats-fair").exists()


def test_sync_lore_appends_notable_actions_section(tmp_path, monkeypatch):
    monkeypatch.setattr("sync_sheet.CAMPAIGNS_DIR", tmp_path)
    lore_rows = [{"subject": "Phandalin", "type": "History", "summary": "A mining town."}]
    action_rows = [{"adventurer": "Tink", "summary": "Cast Grease and set it aflame."}]

    count = sync_lore(lore_rows, action_rows, "thats-fair")

    text = (tmp_path / "thats-fair" / "lore" / "lore.md").read_text()
    assert count == 1
    assert "| Phandalin | History | A mining town. |" in text
    assert "## Notable Actions" in text
    assert "| Tink | Cast Grease and set it aflame. |" in text


def test_sync_lore_omits_notable_actions_heading_when_there_are_none(tmp_path, monkeypatch):
    monkeypatch.setattr("sync_sheet.CAMPAIGNS_DIR", tmp_path)
    lore_rows = [{"subject": "Phandalin", "type": "History", "summary": "A mining town."}]

    sync_lore(lore_rows, [], "thats-fair")

    text = (tmp_path / "thats-fair" / "lore" / "lore.md").read_text()
    assert "Notable Actions" not in text


def test_sync_characters_writes_only_npc_rows(tmp_path, monkeypatch):
    monkeypatch.setattr("sync_sheet.CAMPAIGNS_DIR", tmp_path)
    rows = [
        {"type": "playable", "link": "https://www.dndbeyond.com/characters/123", "name": "", "profession": "", "characteristics": "", "locale": "", "current_villain_status": ""},
        {"type": "npc", "link": "", "name": "Gundren", "profession": "CEO", "characteristics": "Owns a mine", "locale": "Phandalin", "current_villain_status": "Not suspicious"},
    ]

    count = sync_characters(rows, "thats-fair")

    text = (tmp_path / "thats-fair" / "npcs" / "npcs.md").read_text()
    assert count == 1
    assert "title: NPCs" in text
    assert "Gundren" in text
    assert "123" not in text


def test_sync_locations_writes_table(tmp_path, monkeypatch):
    monkeypatch.setattr("sync_sheet.CAMPAIGNS_DIR", tmp_path)
    rows = [{"name": "Phandalin", "type": "Town", "characteristics": "Mining town", "locale": "South"}]

    count = sync_locations(rows, "thats-fair")

    text = (tmp_path / "thats-fair" / "locations" / "locations.md").read_text()
    assert count == 1
    assert "| Phandalin | Town | Mining town | South |" in text


def test_sync_skills_writes_single_guide_page(tmp_path, monkeypatch):
    monkeypatch.setattr("sync_sheet.CAMPAIGNS_DIR", tmp_path)
    rows = [{"skill": "Perception", "usage_rank": "1", "role_playing": "Spot things", "combat": "Win initiative"}]

    count = sync_skills(rows, "thats-fair")

    text = (tmp_path / "thats-fair" / "misc" / "skill-checks-guide.md").read_text()
    assert count == 1
    assert "title: Skill Checks Guide" in text
    assert "| Perception | 1 | Spot things | Win initiative |" in text


def test_sync_misc_writes_one_page_per_row(tmp_path, monkeypatch):
    monkeypatch.setattr("sync_sheet.CAMPAIGNS_DIR", tmp_path)
    rows = [{"name": "Hook for 8/16", "content": "Dear Sir,\n\nA letter arrives."}]

    count = sync_misc(rows, "thats-fair")

    text = (tmp_path / "thats-fair" / "misc" / "hook-for-8-16.md").read_text()
    assert count == 1
    assert "title: Hook for 8/16" in text
    assert "Dear Sir,\n\nA letter arrives." in text


def test_write_page_includes_front_matter_and_body(tmp_path, monkeypatch):
    monkeypatch.setattr("sync_sheet.CAMPAIGNS_DIR", tmp_path)

    write_page("thats-fair", "misc", "my-page", {"title": "My Page", "type": "misc"}, "Body text.")

    text = (tmp_path / "thats-fair" / "misc" / "my-page.md").read_text()
    assert text.startswith("---\n")
    assert "title: My Page" in text
    assert text.strip().endswith("Body text.")
