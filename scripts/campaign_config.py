"""Shared campaign registry helpers used by sync_sheet.py and
fetch_ddb_character.py.

Config: data/campaigns.yaml lists every campaign to sync, each with its own
Sheet ID (see that file for how to add a new one).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CAMPAIGNS_CONFIG_PATH = REPO_ROOT / "data" / "campaigns.yaml"
CAMPAIGNS_DIR = REPO_ROOT / "content" / "campaigns"


def load_campaigns() -> list[dict]:
    data = yaml.safe_load(CAMPAIGNS_CONFIG_PATH.read_text()) or {}
    return data.get("campaigns") or []


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "untitled"
