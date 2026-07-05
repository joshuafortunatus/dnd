"""Fetch character sheets from D&D Beyond for publishing on the site.

D&D Beyond has no official public API. This uses the same undocumented
character JSON endpoint community tools (ddb-proxy, Beyond20) rely on, which
only returns data for characters whose D&D Beyond sharing setting is
"Public". It is unofficial and may change or break without notice.

Because this site is public, ONLY characters explicitly listed in
data/public_characters.yaml are fetched or published — this is a safety
default, not just config, since some characters may belong to other players
who haven't agreed to have their sheet published here. Do not remove the
allow-list check.
"""

from __future__ import annotations

import sys
from pathlib import Path

import requests
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ALLOWLIST_PATH = REPO_ROOT / "data" / "public_characters.yaml"
CAMPAIGNS_DIR = REPO_ROOT / "content" / "campaigns"

CHARACTER_ENDPOINT = "https://character-service.dndbeyond.com/character/v5/character/{id}"


def load_allowlist() -> list[dict]:
    data = yaml.safe_load(ALLOWLIST_PATH.read_text()) or {}
    return data.get("characters") or []


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
    allowlist = load_allowlist()
    if not allowlist:
        print("no characters in data/public_characters.yaml — nothing to fetch")
        return

    failures = 0
    for entry in allowlist:
        character_id = entry["id"]
        slug = entry["slug"]
        try:
            campaign_slug = entry["campaign"]
            character = fetch_character(character_id)
            markdown = render_markdown(character, slug, character_id)
            character_output_path(campaign_slug, slug).write_text(markdown)
            print(f"fetched: {slug} (id={character_id})")
        except Exception as exc:
            failures += 1
            print(f"ERROR fetching character id={character_id} slug={slug}: {exc}", file=sys.stderr)

    if failures:
        print(f"done with {failures} failure(s)", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
