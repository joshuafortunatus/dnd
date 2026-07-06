"""Sync campaign text content from a Google Sheet into content/.

Config: data/campaigns.yaml lists every campaign to sync, each with its own
Sheet ID (see that file for how to add a new one). The sheet needs one tab
per type below, with these exact header columns (see the "that's fair" sheet
for a working example):

  sessions             session_number, date, events
                       One row per event; rows sharing a session_number are
                       grouped into that session's bullet list. date is
                       M/D/YY or M/D/YYYY.
  quests               quest, beneficiary, is_completed
                       is_completed is "yes"/"no" — rendered as a checkmark.
  lore                 subject, type, summary
  notable_actions      adventurer, summary
                       Folded into the bottom of the Lore page.
  characters           type, link, name, profession, characteristics,
                       locale, current_villain_status
                       type is "playable" or "npc". Only npc rows become a
                       page here — playable rows are fetched from D&D Beyond
                       by scripts/fetch_ddb_character.py instead, which reads
                       this same tab for its own allow-list.
  locations            name, type, characteristics, locale
  skills_check_guide   skill, usage_rank, role_playing, combat
  misc                 name, content
                       One page per row.

Images still come from each campaign's Drive folder (scripts/sync_drive.py)
— this script only ever writes text content.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from sheets_client import build_service, read_tab
from sync_drive import CAMPAIGNS_DIR, load_campaigns, slugify

TABLE_ALIGN = ":----"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a GFM table. Cell newlines become <br> (goldmark's unsafe=true
    allows raw HTML) since a literal newline would otherwise break out of the
    table row entirely."""

    def cell(value: str) -> str:
        return str(value).replace("\n", "<br>").replace("|", "\\|").strip()

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(TABLE_ALIGN for _ in headers) + " |",
    ]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


def parse_sheet_date(date_str: str) -> str | None:
    """"6/27/26" -> "2026-06-27". Returns None for blank/unparseable input."""
    date_str = date_str.strip()
    if not date_str:
        return None
    parts = date_str.split("/")
    if len(parts) != 3:
        return None
    month, day, year = (int(part) for part in parts)
    if year < 100:
        year += 2000
    return f"{year:04d}-{month:02d}-{day:02d}"


def write_page(campaign_slug: str, section: str, file_slug: str, front_matter: dict, body: str) -> None:
    out_dir = CAMPAIGNS_DIR / campaign_slug / section
    out_dir.mkdir(parents=True, exist_ok=True)
    text = "---\n" + yaml.safe_dump(front_matter, sort_keys=False, allow_unicode=True) + "---\n\n" + body.strip() + "\n"
    (out_dir / f"{file_slug}.md").write_text(text)


def sync_sessions(rows: list[dict], campaign_slug: str) -> int:
    sessions: dict[str, dict] = {}
    order: list[str] = []
    for row in rows:
        number = row.get("session_number", "").strip()
        if not number:
            continue
        if number not in sessions:
            sessions[number] = {"date": row.get("date", ""), "events": []}
            order.append(number)
        event = row.get("events", "").strip()
        if event:
            sessions[number]["events"].append(event)

    for number in order:
        data = sessions[number]
        front_matter = {"title": f"Session {number}", "type": "sessions"}
        date = parse_sheet_date(data["date"])
        if date:
            front_matter["date"] = date
        body = "\n".join(f"- {event}" for event in data["events"])
        write_page(campaign_slug, "sessions", f"session-{int(number):02d}", front_matter, body)

    return len(order)


def sync_quests(rows: list[dict], campaign_slug: str) -> int:
    quest_rows = [row for row in rows if row.get("quest", "").strip()]
    if not quest_rows:
        return 0
    table_rows = [
        [row.get("quest", ""), row.get("beneficiary", ""), "✔" if row.get("is_completed", "").strip().lower() == "yes" else ""]
        for row in quest_rows
    ]
    body = markdown_table(["Quest", "Beneficiary", "Completed"], table_rows)
    write_page(campaign_slug, "quests", "quest-log", {"title": "Quest Log", "type": "quests"}, body)
    return 1


def sync_lore(lore_rows: list[dict], notable_action_rows: list[dict], campaign_slug: str) -> int:
    lore_rows = [row for row in lore_rows if row.get("subject", "").strip()]
    notable_action_rows = [row for row in notable_action_rows if row.get("adventurer", "").strip()]
    if not lore_rows and not notable_action_rows:
        return 0

    body = markdown_table(
        ["Subject", "Type", "Summary"],
        [[row.get("subject", ""), row.get("type", ""), row.get("summary", "")] for row in lore_rows],
    )
    if notable_action_rows:
        actions_table = markdown_table(
            ["Adventurer", "Summary"],
            [[row.get("adventurer", ""), row.get("summary", "")] for row in notable_action_rows],
        )
        body += "\n\n## Notable Actions\n\n" + actions_table

    write_page(campaign_slug, "lore", "lore", {"title": "Lore", "type": "lore"}, body)
    return 1


CHARACTER_ID_RE = re.compile(r"/characters/(\d+)")


def sync_characters(rows: list[dict], campaign_slug: str) -> int:
    """Only "npc" rows become a page here — "playable" rows are fetched from
    D&D Beyond by fetch_ddb_character.py, which reads this same tab itself."""
    npc_rows = [row for row in rows if row.get("type", "").strip().lower() == "npc"]
    if not npc_rows:
        return 0
    table = markdown_table(
        ["Name", "Profession", "Characteristics", "Locale", "Current Villain Status"],
        [
            [
                row.get("name", ""),
                row.get("profession", ""),
                row.get("characteristics", ""),
                row.get("locale", ""),
                row.get("current_villain_status", ""),
            ]
            for row in npc_rows
        ],
    )
    write_page(campaign_slug, "npcs", "npcs", {"title": "NPCs", "type": "npcs"}, table)
    return 1


def sync_locations(rows: list[dict], campaign_slug: str) -> int:
    location_rows = [row for row in rows if row.get("name", "").strip()]
    if not location_rows:
        return 0
    table = markdown_table(
        ["Name", "Type", "Characteristics", "Locale"],
        [[row.get("name", ""), row.get("type", ""), row.get("characteristics", ""), row.get("locale", "")] for row in location_rows],
    )
    write_page(campaign_slug, "locations", "locations", {"title": "Locations", "type": "locations"}, table)
    return 1


def sync_skills(rows: list[dict], campaign_slug: str) -> int:
    skill_rows = [row for row in rows if row.get("skill", "").strip()]
    if not skill_rows:
        return 0
    table = markdown_table(
        ["Skill", "Usage Rank", "Role Playing", "Combat"],
        [[row.get("skill", ""), row.get("usage_rank", ""), row.get("role_playing", ""), row.get("combat", "")] for row in skill_rows],
    )
    write_page(campaign_slug, "misc", "skill-checks-guide", {"title": "Skill Checks Guide", "type": "misc"}, table)
    return 1


def sync_misc(rows: list[dict], campaign_slug: str) -> int:
    count = 0
    for row in rows:
        name = row.get("name", "").strip()
        content = row.get("content", "").strip()
        if not name:
            continue
        write_page(campaign_slug, "misc", slugify(name), {"title": name, "type": "misc"}, content)
        count += 1
    return count


def sync_campaign(service, campaign: dict) -> int:
    sheet_id = campaign["sheet_id"]
    slug = campaign["slug"]
    changed = 0
    changed += sync_sessions(read_tab(service, sheet_id, "sessions"), slug)
    changed += sync_quests(read_tab(service, sheet_id, "quests"), slug)
    changed += sync_lore(read_tab(service, sheet_id, "lore"), read_tab(service, sheet_id, "notable_actions"), slug)
    changed += sync_characters(read_tab(service, sheet_id, "characters"), slug)
    changed += sync_locations(read_tab(service, sheet_id, "locations"), slug)
    changed += sync_skills(read_tab(service, sheet_id, "skills_check_guide"), slug)
    changed += sync_misc(read_tab(service, sheet_id, "misc"), slug)
    return changed


def main() -> None:
    campaigns = load_campaigns()
    if not campaigns:
        print("no campaigns configured in data/campaigns.yaml — nothing to sync")
        return

    service = build_service()
    total_changed = 0
    for campaign in campaigns:
        changed = sync_campaign(service, campaign)
        total_changed += changed
        print(f"{campaign['slug']}: {changed} page(s) synced")
    print(f"done: {total_changed} page(s) synced total")


if __name__ == "__main__":
    main()
