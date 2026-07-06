"""Fetch character sheets from D&D Beyond for publishing on the site.

D&D Beyond has no official public API. This uses the same undocumented
character JSON endpoint community tools (ddb-proxy, Beyond20) rely on, which
only returns data for characters whose D&D Beyond sharing setting is
"Public". It is unofficial and may change or break without notice.

Because this site is public, ONLY rows marked type="playable" in a campaign's
Google Sheet "characters" tab are fetched or published — this is a safety
default, not just config, since some rows may belong to other players who
haven't agreed to have their sheet published here. Do not remove this filter.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import requests
import yaml

from sheets_client import build_service, read_tab
from sync_drive import load_campaigns, slugify

REPO_ROOT = Path(__file__).resolve().parent.parent
CAMPAIGNS_DIR = REPO_ROOT / "content" / "campaigns"

CHARACTER_ENDPOINT = "https://character-service.dndbeyond.com/character/v5/character/{id}"
CHARACTER_ID_RE = re.compile(r"/characters/(\d+)")
NICKNAME_RE = re.compile(r'"([^"]+)"')


def character_id_from_link(link: str) -> int | None:
    match = CHARACTER_ID_RE.search(link)
    return int(match.group(1)) if match else None


def character_slug(name: str, fallback: str) -> str:
    """Prefer a quoted nickname (e.g. 'Bunco "Tink" Dalmarian' -> "tink") since
    that's what players actually go by; otherwise fall back to the first
    word of the full name, then to the raw D&D Beyond character id."""
    match = NICKNAME_RE.search(name)
    if match:
        return slugify(match.group(1))
    first_word = name.split()[0] if name.split() else fallback
    return slugify(first_word)


def load_playable_character_ids(service, sheet_id: str) -> list[int]:
    character_ids = []
    for row in read_tab(service, sheet_id, "characters"):
        if row.get("type", "").strip().lower() != "playable":
            continue
        character_id = character_id_from_link(row.get("link", ""))
        if character_id is None:
            print(f"WARN: playable row has no parseable D&D Beyond link: {row}", file=sys.stderr)
            continue
        character_ids.append(character_id)
    return character_ids


def fetch_character(character_id: int) -> dict:
    response = requests.get(CHARACTER_ENDPOINT.format(id=character_id), timeout=30)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success", True):
        raise ValueError(payload.get("message", "unknown error from D&D Beyond"))
    return payload["data"]


def render_markdown(character: dict, slug: str, character_id: int) -> str:
    stats = {s["id"]: s["value"] for s in character.get("stats", [])}
    # D&D Beyond ability score stat ids: 1 str, 2 dex, 3 con, 4 int, 5 wis, 6 cha
    ability_scores = {
        "str": stats.get(1, 10),
        "dex": stats.get(2, 10),
        "con": stats.get(3, 10),
        "int": stats.get(4, 10),
        "wis": stats.get(5, 10),
        "cha": stats.get(6, 10),
    }
    classes = character.get("classes", [])
    class_name = classes[0]["definition"]["name"] if classes else "Unknown"
    level = sum(c.get("level", 0) for c in classes) or 1
    species_name = (character.get("race") or {}).get("fullName", "Unknown")
    name = character.get("name", slug)

    front_matter = {
        "title": name,
        "type": "characters",
        "species": species_name,
        "class": class_name,
        "level": level,
        "ability_scores": ability_scores,
        "ddb_url": f"https://www.dndbeyond.com/characters/{character_id}",
    }
    return "---\n" + yaml.safe_dump(front_matter, sort_keys=False, allow_unicode=True) + "---\n"


def character_output_path(campaign_slug: str, slug: str) -> Path:
    out_dir = CAMPAIGNS_DIR / campaign_slug / "characters"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{slug}.md"


def main() -> None:
    campaigns = load_campaigns()
    if not campaigns:
        print("no campaigns configured in data/campaigns.yaml — nothing to fetch")
        return

    service = build_service()
    fetched = 0
    failures = 0
    for campaign in campaigns:
        campaign_slug = campaign["slug"]
        for character_id in load_playable_character_ids(service, campaign["sheet_id"]):
            try:
                character = fetch_character(character_id)
                slug = character_slug(character.get("name", ""), fallback=str(character_id))
                markdown = render_markdown(character, slug, character_id)
                character_output_path(campaign_slug, slug).write_text(markdown)
                fetched += 1
                print(f"fetched: {slug} (id={character_id})")
            except Exception as exc:
                failures += 1
                print(f"ERROR fetching character id={character_id} campaign={campaign_slug}: {exc}", file=sys.stderr)

    print(f"done: {fetched} character(s) fetched" + (f", {failures} failure(s)" if failures else ""))
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
