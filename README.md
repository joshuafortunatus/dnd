# dnd

A public GitHub Pages site consolidating D&D campaign notes (from a Google
Sheet + Drive folder) and character sheets (from D&D Beyond). Built with
[Hugo](https://gohugo.io/). Supports multiple campaigns.

Once deployed: https://joshuafortunatus.github.io/dnd/

## How it fits together

- `content/campaigns/<slug>/` — Hugo pages per campaign: `sessions/`,
  `quests/`, `lore/`, `characters/`, `npcs/`, `locations/`, `misc/`. A page's
  kind is tracked via an explicit `type` front matter field, not its
  directory.
- `data/campaigns.yaml` — registry of every campaign to sync, each with its
  own Drive folder ID (images) and Google Sheet ID (text). See the comments
  in that file for how to add a new campaign.
- `scripts/sync_drive.py` — downloads every image found in a campaign's
  Drive folder (including nested subfolders) into
  `static/images/campaigns/<slug>/`.
- `scripts/sync_sheet.py` — reads a campaign's Google Sheet (one tab per
  content type) and writes the corresponding Hugo content pages. See that
  script's docstring for each tab's expected columns.
- `scripts/sheets_client.py` — shared Google Sheets API helper used by
  `sync_sheet.py` and `fetch_ddb_character.py`.
- `scripts/fetch_ddb_character.py` — fetches character sheets from D&D
  Beyond for the rows marked `type: playable` in a campaign's Sheet
  `characters` tab, and *only* those rows.
- `.github/workflows/sync-content.yml` — runs all three scripts daily,
  commits any changes, and triggers a redeploy.
- `.github/workflows/deploy.yml` — builds the Hugo site and publishes it to
  GitHub Pages on every push to `main`.

## ⚠️ Before adding a character

**This repo and site are public.** `fetch_ddb_character.py` only fetches and
publishes characters whose row in a campaign's Sheet `characters` tab has
`type: playable` — this is intentional, not a bug. If a character belongs to
someone other than you, get their OK before marking their row `playable`.
D&D Beyond also has no official public API; the endpoint this uses is
unofficial (reverse-engineered by community tools like
`ddb-proxy`/`Beyond20`) and only returns data for characters whose D&D Beyond
sharing setting is "Public" — it could change or stop working without
notice.

## One-time setup

### 1. Google Cloud service account

1. In Google Cloud Console, create a project (or reuse one) and enable the
   **Google Drive API** and **Google Sheets API**.
2. Create a **service account**, generate a JSON key for it.
3. Add the full contents of the JSON key as a repo secret named
   `GOOGLE_CREDENTIALS_JSON`: Settings → Secrets and variables → Actions →
   New repository secret.

### 2. Add a campaign

1. Create a Google Drive folder with an `images` subfolder for that
   campaign's images, and a Google Sheet for its text content — one tab per
   type: `sessions`, `quests`, `lore`, `notable_actions`, `characters`,
   `locations`, `skills_check_guide`, `misc`. See `scripts/sync_sheet.py`'s
   docstring for each tab's expected columns.
2. Share both the Drive folder and the Sheet as a **Viewer** with the
   service account's email address (found in the JSON key as
   `client_email`).
3. Add an entry to `data/campaigns.yaml` with the folder's ID (from its
   share URL) and the Sheet's ID (from its URL). Neither ID is sensitive, so
   they live in that file rather than as secrets.
4. Scaffold the campaign page: `hugo new campaigns/<slug>/_index.md` (fill
   in `hero_image` with a real image under
   `static/images/campaigns/<slug>/`).
5. Commit and push, or wait for the next scheduled sync.

### 3. Add a playable character

1. Open the character on D&D Beyond, make sure its privacy/sharing setting
   is **Public**.
2. In the campaign's Sheet `characters` tab, add a row with `type` set to
   `playable` and `link` set to the character's D&D Beyond URL.
3. Commit and push, or wait for the next scheduled sync — the character's
   slug and content are derived automatically from the fetched sheet data.

### 4. Enable GitHub Pages

Settings → Pages → Source: **GitHub Actions**. (If this was already
configured via the API when the repo was set up, you can skip this.)

## Running locally

```bash
# Site
hugo server -D          # http://localhost:1313/dnd/

# Content sync (requires GOOGLE_CREDENTIALS_JSON in the environment)
pip install -r scripts/requirements.txt
python scripts/sync_drive.py
python scripts/sync_sheet.py
python scripts/fetch_ddb_character.py

# Tests
pytest scripts/tests/
```
