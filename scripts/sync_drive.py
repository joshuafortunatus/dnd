"""Sync campaign notes and images from a Google Drive folder into content/.

Auth: expects a service-account JSON key in the GOOGLE_CREDENTIALS_JSON env var
(same pattern used in this user's other repos, e.g. munibot/main.py). The
service account must be shared as a viewer on the target Drive folder.

Config: DRIVE_FOLDER_ID env var (or --folder-id) points at the root folder to
sync. Within that folder:
  - Google Docs are exported to Markdown and written under content/sessions/.
  - Everything else (images, maps) is downloaded into static/images/.

Re-running only rewrites a file if Drive's modifiedTime is newer than the
last synced copy (tracked in data/.drive_sync_state.json).
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
from pathlib import Path

import requests
import yaml
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = REPO_ROOT / "data" / ".drive_sync_state.json"
SESSIONS_DIR = REPO_ROOT / "content" / "sessions"
IMAGES_DIR = REPO_ROOT / "static" / "images"

GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
GOOGLE_FOLDER_MIME = "application/vnd.google-apps.folder"


def load_credentials() -> service_account.Credentials:
    raw = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if not raw:
        raise SystemExit("GOOGLE_CREDENTIALS_JSON is not set — cannot authenticate to Drive.")
    info = json.loads(raw)
    return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)


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
                fields="nextPageToken, files(id, name, mimeType, modifiedTime)",
                pageToken=page_token,
            )
            .execute()
        )
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return files


def export_doc_markdown(service, file_id: str) -> str:
    try:
        return service.files().export(fileId=file_id, mimeType="text/markdown").execute().decode("utf-8")
    except Exception:
        # Fallback for environments where the markdown export type isn't available yet.
        html = service.files().export(fileId=file_id, mimeType="text/html").execute().decode("utf-8")
        try:
            import html2text

            return html2text.html2text(html)
        except ImportError:
            print(
                f"WARN: markdown export failed for {file_id} and html2text isn't installed; "
                "writing raw HTML instead.",
                file=sys.stderr,
            )
            return html


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

        if entry["mimeType"] == GOOGLE_FOLDER_MIME:
            changed += sync_folder(service, entry["id"], campaign_slug, state)
            continue

        slug = slugify(entry["name"])
        if entry["mimeType"] == GOOGLE_DOC_MIME:
            body = export_doc_markdown(service, entry["id"])
            out_dir = SESSIONS_DIR / campaign_slug
            out_dir.mkdir(parents=True, exist_ok=True)
            front_matter = {
                "title": entry["name"],
                "campaigns_tag": [campaign_slug],
            }
            out_path = out_dir / f"{slug}.md"
            out_path.write_text(
                "---\n" + yaml.safe_dump(front_matter, sort_keys=False) + "---\n\n" + body
            )
        else:
            ext = Path(entry["name"]).suffix or ""
            out_path = IMAGES_DIR / f"{slug}{ext}"
            download_binary(service, entry["id"], out_path)

        state[entry["id"]] = modified
        changed += 1
        print(f"synced: {entry['name']}")

    return changed


def main() -> None:
    folder_id = os.environ.get("DRIVE_FOLDER_ID")
    if not folder_id:
        raise SystemExit("DRIVE_FOLDER_ID is not set — nothing to sync.")
    campaign_slug = os.environ.get("DRIVE_CAMPAIGN_SLUG", "example-campaign")

    credentials = load_credentials()
    service = build("drive", "v3", credentials=credentials)

    state = load_state()
    changed = sync_folder(service, folder_id, campaign_slug, state)
    save_state(state)
    print(f"done: {changed} file(s) synced")


if __name__ == "__main__":
    main()
