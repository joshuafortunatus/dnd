"""Sync campaign notes and images from a Google Drive folder into content/.

Auth: expects a service-account JSON key in the GOOGLE_CREDENTIALS_JSON env var
(same pattern used in this user's other repos, e.g. munibot/main.py). The
service account must be shared as a viewer on the target Drive folder.

Config: DRIVE_FOLDER_ID env var (or --folder-id) points at the root folder to
sync. Within that folder:
  - Google Docs directly in the root default to content/sessions/. To route
    docs elsewhere, put them in a Drive subfolder named "Sessions", "Quests",
    or "Lore" (case-insensitive) — nested subfolders inherit their parent's
    section unless they're themselves named one of those three.
  - Every image is downloaded into static/images/ AND gets a small content
    stub written under content/images/, so the site's Images tab can list
    all of a campaign's images regardless of which Drive subfolder they're in.

Re-running only rewrites a file if Drive's modifiedTime is newer than the
last synced copy (tracked in data/.drive_sync_state.json).
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlparse

import requests
import yaml
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = REPO_ROOT / "data" / ".drive_sync_state.json"
CONTENT_DIR = REPO_ROOT / "content"
IMAGES_DIR = REPO_ROOT / "static" / "images"
IMAGES_CONTENT_DIR = REPO_ROOT / "content" / "images"

GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
GOOGLE_FOLDER_MIME = "application/vnd.google-apps.folder"
GOOGLE_SHORTCUT_MIME = "application/vnd.google-apps.shortcut"

DOC_SECTIONS = {"sessions", "quests", "lore"}
DEFAULT_DOC_SECTION = "sessions"

INLINE_IMAGE_RE = re.compile(r"data:image/(?P<ext>png|jpe?g|gif);base64,(?P<data>[A-Za-z0-9+/=]+)")


def site_base_path() -> str:
    """The baseURL's path segment (e.g. "/dnd"), so generated links work under GitHub Pages' repo subpath."""
    config = tomllib.loads((REPO_ROOT / "hugo.toml").read_text())
    return urlparse(config.get("baseURL", "")).path.rstrip("/")


def extract_inline_images(body: str, slug: str) -> str:
    """Google Docs export pasted screenshots as inline base64 data URIs, which bloats
    the markdown file with megabytes of text. Pull each one out into a real file under
    static/images/ and rewrite the reference to a normal path."""
    base_path = site_base_path()
    counter = 0

    def replace(match: re.Match) -> str:
        nonlocal counter
        counter += 1
        ext = "jpg" if match["ext"] == "jpeg" else match["ext"]
        filename = f"{slug}-inline-{counter}.{ext}"
        (IMAGES_DIR / filename).write_bytes(base64.b64decode(match["data"]))
        return f"{base_path}/images/{filename}"

    return INLINE_IMAGE_RE.sub(replace, body)


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
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, shortcutDetails)",
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


def sync_folder(
    service, folder_id: str, campaign_slug: str, state: dict, section: str = DEFAULT_DOC_SECTION
) -> int:
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
            child_section = slugify(entry["name"])
            if child_section not in DOC_SECTIONS:
                child_section = section
            changed += sync_folder(service, content_id, campaign_slug, state, section=child_section)
            state[entry["id"]] = modified
            continue

        slug = slugify(entry["name"])
        try:
            if content_mime == GOOGLE_DOC_MIME:
                body = export_doc_markdown(service, content_id)
                body = extract_inline_images(body, slug)
                out_dir = CONTENT_DIR / section / campaign_slug
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
                image_path = IMAGES_DIR / f"{slug}{ext}"
                download_binary(service, content_id, image_path)
                write_image_stub(campaign_slug, entry["name"], slug, image_path)
        except Exception as exc:
            print(f"WARN: failed to sync '{entry['name']}': {exc}", file=sys.stderr)
            continue

        state[entry["id"]] = modified
        changed += 1
        print(f"synced: {entry['name']}")

    return changed


def write_image_stub(campaign_slug: str, name: str, slug: str, image_path: Path) -> None:
    """Write a lightweight content page for a synced image so the site's Images tab
    can list it via the same Section-based lookup used for sessions/quests/etc."""
    out_dir = IMAGES_CONTENT_DIR / campaign_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    front_matter = {
        "title": name,
        "campaigns_tag": [campaign_slug],
        "image": f"{site_base_path()}/images/{image_path.name}",
    }
    (out_dir / f"{slug}.md").write_text("---\n" + yaml.safe_dump(front_matter, sort_keys=False) + "---\n")


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
