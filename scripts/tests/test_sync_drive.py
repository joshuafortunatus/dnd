import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sync_drive import extract_inline_images, load_state, save_state, slugify, split_doc_sections

TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


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


def test_extract_inline_images_writes_file_and_rewrites_reference(tmp_path, monkeypatch):
    monkeypatch.setattr("sync_drive.STATIC_IMAGES_DIR", tmp_path)
    monkeypatch.setattr("sync_drive.site_base_path", lambda: "/dnd")
    b64 = base64.b64encode(TINY_PNG).decode()
    body = f"![][image1]\n\n[image1]: <data:image/png;base64,{b64}>\n"

    result = extract_inline_images(body, slug="my-doc", campaign_slug="thats-fair")

    assert "data:image" not in result
    assert "[image1]: </dnd/images/campaigns/thats-fair/my-doc-inline-1.png>" in result
    assert (tmp_path / "campaigns" / "thats-fair" / "my-doc-inline-1.png").read_bytes() == TINY_PNG


def test_extract_inline_images_leaves_body_unchanged_when_no_images(monkeypatch):
    monkeypatch.setattr("sync_drive.site_base_path", lambda: "/dnd")
    body = "Just some plain session notes, no images here."

    assert extract_inline_images(body, slug="my-doc", campaign_slug="thats-fair") == body


def test_split_doc_sections_separates_known_type_headings():
    body = (
        "# Summary\nSession recap text.\n"
        "# Quests\nQuest list text.\n"
        "# NPCs\nNPC table text.\n"
    )

    sections = dict(split_doc_sections(body))

    assert set(sections.keys()) == {None, "quests", "npcs"}
    assert "Session recap text." in sections[None]
    assert "# Summary" in sections[None]
    assert sections["quests"].strip() == "Quest list text."
    assert sections["npcs"].strip() == "NPC table text."


def test_split_doc_sections_strips_duplicate_label_line():
    body = "# Locations\n\nLocations\n\n| Name |\n| :---- |\n| Phandalin |\n"

    sections = dict(split_doc_sections(body))

    assert "Locations\n\n" not in sections["locations"]
    assert sections["locations"].startswith("| Name |")


def test_split_doc_sections_no_headings_returns_single_default_bucket():
    body = "Just a plain doc with no headings at all."

    sections = split_doc_sections(body)

    assert len(sections) == 1
    assert sections[0][0] is None
    assert sections[0][1].strip() == body
