# dnd

A public GitHub Pages site consolidating D&D campaign notes (from Google Drive)
and character sheets (from D&D Beyond). Built with [Hugo](https://gohugo.io/).

Once deployed: https://joshuafortunatus.github.io/dnd/

## How it fits together

- `content/` — Hugo pages: `campaigns/`, `sessions/`, `characters/`, `npcs/`, `locations/`.
- `scripts/sync_drive.py` — pulls Google Docs (as Markdown) and images from a
  Google Drive folder into `content/sessions/` and `static/images/`.
- `scripts/fetch_ddb_character.py` — fetches character sheets from D&D Beyond
  for the characters listed in `data/public_characters.yaml`, and *only*
  those characters.
- `.github/workflows/sync-content.yml` — runs both scripts daily, commits any
  changes, and triggers a redeploy.
- `.github/workflows/deploy.yml` — builds the Hugo site and publishes it to
  GitHub Pages on every push to `main`.

## ⚠️ Before adding a character

**This repo and site are public.** `fetch_ddb_character.py` only fetches and
publishes characters explicitly listed in `data/public_characters.yaml` — this
is intentional, not a bug. If a character belongs to someone other than you,
get their OK before adding their character ID to the allow-list. D&D Beyond
also has no official public API; the endpoint this uses is unofficial
(reverse-engineered by community tools like `ddb-proxy`/`Beyond20`) and only
returns data for characters whose D&D Beyond sharing setting is "Public" — it
could change or stop working without notice.

## One-time setup

### 1. Google Drive sync

1. In Google Cloud Console, create a project (or reuse one) and enable the
   **Google Drive API**.
2. Create a **service account**, generate a JSON key for it.
3. Share the Drive folder containing your campaign docs/images with the
   service account's email address (found in the JSON key as `client_email`),
   as a Viewer.
4. Add the full contents of the JSON key as a repo secret named
   `GOOGLE_CREDENTIALS_JSON`: Settings → Secrets and variables → Actions →
   New repository secret.
5. Add the target Drive folder's ID as a repo **variable** named
   `DRIVE_FOLDER_ID` (the ID is the last path segment of the folder's URL):
   Settings → Secrets and variables → Actions → Variables tab.

### 2. D&D Beyond characters

1. Open the character on D&D Beyond, make sure its privacy/sharing setting is
   **Public**.
2. Copy the numeric ID from the character's URL
   (`https://www.dndbeyond.com/characters/<id>`).
3. Add an entry to `data/public_characters.yaml`:
   ```yaml
   characters:
     - id: 123456789
       slug: my-character
   ```
4. Commit and push, or wait for the next scheduled sync.

### 3. Enable GitHub Pages

Settings → Pages → Source: **GitHub Actions**. (If this was already
configured via the API when the repo was set up, you can skip this.)

## Running locally

```bash
# Site
hugo server -D          # http://localhost:1313/dnd/

# Content sync (requires the env vars described above)
pip install -r scripts/requirements.txt
python scripts/sync_drive.py
python scripts/fetch_ddb_character.py
```
