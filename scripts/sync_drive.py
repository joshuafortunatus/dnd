"""Sync campaign images from a Google Drive folder into static/.

Auth: expects a service-account JSON key in the GOOGLE_CREDENTIALS_JSON env var
(same pattern used in this user's other repos, e.g. munibot/main.py). The
service account must be shared as a viewer on the target Drive folder.

Config: data/campaigns.yaml lists every campaign to sync, each with its own
Drive folder ID (see that file for how to add a new one). Every image found
anywhere in that folder — including nested subfolders, e.g. the "images"
subfolder each campaign's Drive folder is organized around — is downloaded
into static/images/campaigns/<slug>/. That's the only thing this script does;
text content comes from each campaign's Google Sheet instead (see
scripts/sync_sheet.py). Images have to live under static/ for Hugo to serve
them as real URLs — the site's Images tab lists them by reading that
directory directly at build time (readDir in hub.html) rather than via a
separate content stub page per image.

Re-running only re-downloads a file if Drive's modifiedTime is newer than the
last synced copy (tracked in data/.drive_sync_state.json).
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
from pathlib import Path

import yaml
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = REPO_ROOT / "data" / ".drive_sync_state.json"
CAMPAIGNS_CONFIG_PATH = REPO_ROOT / "data" / "campaigns.yaml"
CAMPAIGNS_DIR = REPO_ROOT / "content" / "campaigns"
STATIC_IMAGES_DIR = REPO_ROOT / "static" / "images"

GOOGLE_FOLDER_MIME = "application/vnd.google-apps.folder"
GOOGLE_SHORTCUT_MIME = "application/vnd.google-apps.shortcut"


def campaign_images_dir(campaign_slug: str) -> Path:
    return STATIC_IMAGES_DIR / "campaigns" / campaign_slug


def load_credentials() -> service_account.Credentials:
    raw = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if not raw:
        raise SystemExit("GOOGLE_CREDENTIALS_JSON is not set — cannot authenticate to Drive.")
    info = json.loads(raw)
    return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)


def load_campaigns() -> list[dict]:
    data = yaml.safe_load(CAMPAIGNS_CONFIG_PATH.read_text()) or {}
    return data.get("campaigns") or []


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True))


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "untitled"


def list_children(service, folder_id: str) -> list[dict]:
    files: list[dict] = []
    page_token = None
    while True:
        response = (
            service.files()
            .list(
                q=f"'{folder_id}' in parents and trashed = false",
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, shortcutDetails)",
                pageToken=page_token,
            )
            .execute()
        )
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return files


def download_binary(service, file_id: str, dest: Path) -> None:
    request = service.files().get_media(fileId=file_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with io.FileIO(dest, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()


def sync_folder(service, folder_id: str, campaign_slug: str, state: dict) -> int:
    changed = 0
    for entry in list_children(service, folder_id):
        modified = entry["modifiedTime"]
        if state.get(entry["id"]) == modified:
            continue  # unchanged since last sync

        content_id, content_mime = entry["id"], entry["mimeType"]
        if content_mime == GOOGLE_SHORTCUT_MIME:
            target = entry.get("shortcutDetails") or {}
            if not target.get("targetId"):
                print(f"WARN: shortcut '{entry['name']}' has no target, skipping", file=sys.stderr)
                continue
            content_id, content_mime = target["targetId"], target.get("targetMimeType")

        if content_mime == GOOGLE_FOLDER_MIME:
            changed += sync_folder(service, content_id, campaign_slug, state)
            state[entry["id"]] = modified
            continue

        if not content_mime.startswith("image/"):
            continue  # not an image (e.g. the campaign's own Google Sheet) — nothing to do here

        try:
            ext = Path(entry["name"]).suffix or ""
            image_slug = slugify(Path(entry["name"]).stem)
            image_path = campaign_images_dir(campaign_slug) / f"{image_slug}{ext}"
            download_binary(service, content_id, image_path)
        except Exception as exc:
            print(f"WARN: failed to sync '{entry['name']}': {exc}", file=sys.stderr)
            continue

        state[entry["id"]] = modified
        changed += 1
        print(f"synced: {entry['name']}")

    return changed


def main() -> None:
    campaigns = load_campaigns()
    if not campaigns:
        print("no campaigns configured in data/campaigns.yaml — nothing to sync")
        return

    credentials = load_credentials()
    service = build("drive", "v3", credentials=credentials)

    state = load_state()
    total_changed = 0
    for campaign in campaigns:
        changed = sync_folder(service, campaign["drive_folder_id"], campaign["slug"], state)
        total_changed += changed
        print(f"{campaign['slug']}: {changed} image(s) synced")
    save_state(state)
    print(f"done: {total_changed} image(s) synced total")


if __name__ == "__main__":
    main()
