import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fetch_ddb_character import character_output_path, load_allowlist, render_markdown

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


def test_load_allowlist_reads_characters_list(tmp_path, monkeypatch):
    allowlist_path = tmp_path / "public_characters.yaml"
    allowlist_path.write_text("characters:\n  - id: 123\n    slug: thalia\n    campaign: thats-fair\n")
    monkeypatch.setattr("fetch_ddb_character.ALLOWLIST_PATH", allowlist_path)

    assert load_allowlist() == [{"id": 123, "slug": "thalia", "campaign": "thats-fair"}]


def test_load_allowlist_empty_file_returns_empty_list(tmp_path, monkeypatch):
    allowlist_path = tmp_path / "public_characters.yaml"
    allowlist_path.write_text("")
    monkeypatch.setattr("fetch_ddb_character.ALLOWLIST_PATH", allowlist_path)

    assert load_allowlist() == []
