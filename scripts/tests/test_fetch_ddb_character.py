import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fetch_ddb_character import (
    character_id_from_link,
    character_output_path,
    character_slug,
    load_playable_character_ids,
    render_markdown,
)

SAMPLE_CHARACTER = {
    "name": "Thalia Nightshade",
    "race": {"fullName": "Half-Elf"},
    "classes": [{"level": 5, "definition": {"name": "Wizard"}}],
    "stats": [
        {"id": 1, "value": 8},
        {"id": 2, "value": 14},
        {"id": 3, "value": 12},
        {"id": 4, "value": 18},
        {"id": 5, "value": 10},
        {"id": 6, "value": 13},
    ],
}


def test_render_markdown_includes_front_matter_fields():
    markdown = render_markdown(SAMPLE_CHARACTER, slug="thalia", character_id=123456789)

    assert markdown.startswith("---\n")
    assert "title: Thalia Nightshade" in markdown
    assert "type: characters" in markdown
    assert "species: Half-Elf" in markdown
    assert "class: Wizard" in markdown
    assert "level: 5" in markdown
    assert "ddb_url: https://www.dndbeyond.com/characters/123456789" in markdown


def test_render_markdown_falls_back_when_fields_missing():
    markdown = render_markdown({}, slug="unnamed-npc", character_id=1)

    assert "title: unnamed-npc" in markdown
    assert "species: Unknown" in markdown
    assert "class: Unknown" in markdown
    assert "level: 1" in markdown


def test_character_output_path_nests_under_campaign(tmp_path, monkeypatch):
    monkeypatch.setattr("fetch_ddb_character.CAMPAIGNS_DIR", tmp_path)

    path = character_output_path("thats-fair", "thalia")

    assert path == tmp_path / "thats-fair" / "characters" / "thalia.md"
    assert path.parent.is_dir()


def test_character_id_from_link_extracts_the_numeric_id():
    assert character_id_from_link("https://www.dndbeyond.com/characters/149228927") == 149228927


def test_character_id_from_link_ignores_trailing_path_segment():
    assert character_id_from_link("https://www.dndbeyond.com/characters/126491174/Z7AIQ9") == 126491174


def test_character_id_from_link_returns_none_when_unparseable():
    assert character_id_from_link("") is None
    assert character_id_from_link("not a link") is None


def test_character_slug_prefers_quoted_nickname():
    assert character_slug('Bunco "Tink" Dalmarian', fallback="1") == "tink"


def test_character_slug_falls_back_to_first_word_when_no_nickname():
    assert character_slug("Nenkelde Ravenberry", fallback="1") == "nenkelde"


def test_character_slug_falls_back_to_id_when_name_is_blank():
    assert character_slug("", fallback="149228927") == "149228927"


def test_load_playable_character_ids_filters_to_playable_rows(monkeypatch):
    rows = [
        {"type": "playable", "link": "https://www.dndbeyond.com/characters/111"},
        {"type": "npc", "link": ""},
        {"type": "playable", "link": "https://www.dndbeyond.com/characters/222/SomeSlug"},
    ]
    monkeypatch.setattr("fetch_ddb_character.read_tab", lambda service, sheet_id, tab: rows)

    assert load_playable_character_ids(service=None, sheet_id="sheet-1") == [111, 222]


def test_load_playable_character_ids_skips_unparseable_links(monkeypatch):
    rows = [{"type": "playable", "link": "not a link"}]
    monkeypatch.setattr("fetch_ddb_character.read_tab", lambda service, sheet_id, tab: rows)

    assert load_playable_character_ids(service=None, sheet_id="sheet-1") == []
