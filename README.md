# dnd

Public GitHub Pages site for D&D campaign notes (synced from Google Sheets) and
character sheets (synced from D&D Beyond), plus a password-gated DM Portal
(NPCs, travel, settlements, journal, conflicts, magic items, bastions, file
sharing). Built with [Hugo](https://gohugo.io/). Supports multiple campaigns.

https://joshuafortunatus.github.io/dnd/

## Structure

- `content/campaigns/<slug>/` — campaign pages (`sessions/`, `quests/`, `lore/`,
  `characters/`, `npcs/`, `locations/`, `misc/`), typed via front matter
- `data/campaigns.yaml` — campaign registry (Sheet IDs)
- `scripts/sync_sheet.py` — Google Sheet → Hugo content
- `scripts/fetch_ddb_character.py` — D&D Beyond → character pages (only rows
  marked `type: playable`)
- `worker/ddb-character-proxy.js` — Cloudflare Worker: CORS proxy, cross-device
  DM Portal sync, File Library uploads (R2)
- `.github/workflows/` — `sync-content.yml` (daily content sync), `deploy.yml`
  (build + publish on push to `main`), `ci.yml` (build + test on PRs)

## ⚠️ Character privacy

`fetch_ddb_character.py` only publishes characters marked `type: playable` in a
campaign's Sheet. Get consent before marking someone else's character
`playable` — this repo/site is public. The D&D Beyond fetch is unofficial and
only works for characters shared as "Public".

## Setup

1. Google Cloud: enable the Sheets API, create a service account, add its JSON
   key as repo secret `GOOGLE_CREDENTIALS_JSON`.
2. New campaign: create a Sheet (tabs: `sessions`, `quests`, `lore`,
   `notable_actions`, `characters`, `locations`, `skills_check_guide`, `misc` —
   see `sync_sheet.py`'s docstring for columns), share it Viewer with the
   service account's email, add it to `data/campaigns.yaml`, scaffold with
   `hugo new campaigns/<slug>/_index.md`.
3. New playable character: set D&D Beyond sharing to Public, add a
   `characters` row with `type: playable` and `link`.
4. GitHub Pages: Settings → Pages → Source: GitHub Actions.

## Local dev

```bash
hugo server -D                              # http://localhost:1313/dnd/

pip install -r scripts/requirements.txt
GOOGLE_CREDENTIALS_JSON='...' python scripts/sync_sheet.py
GOOGLE_CREDENTIALS_JSON='...' python scripts/fetch_ddb_character.py

pytest scripts/tests/
```
