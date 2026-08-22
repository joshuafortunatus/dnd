---
title: "{{ replace .File.ContentBaseName "-" " " | title }}"
date: {{ .Date }}
layout: "hub"
system: "D&D 5e"
status: "active"
# Controls order in the homepage campaign picker (lower = shown first).
# New campaigns default to 0, which sorts before all existing campaigns —
# set this explicitly if you want it to land elsewhere in the list.
weight: 0
# Path (relative to static/) to a real image under
# static/images/campaigns/<slug>/ — falls back to the site-wide
# background_image (hugo.toml) if left blank.
hero_image: ""
# Gates the whole campaign hub page behind a client-side password prompt
# (obscurity, not real security — the gated content still ships in the
# page's HTML, so anyone using view-source or disabling JS can read it
# regardless of the password). Leave blank to skip the gate entirely — the
# hub renders wide open, no password prompt at all (this is the default
# for existing campaigns too).
#
# To generate a hash, open a browser console (any page) and run:
#
#   crypto.subtle.digest("SHA-256", new TextEncoder().encode("your-password"))
#     .then(b => console.log(Array.from(new Uint8Array(b))
#       .map(x => x.toString(16).padStart(2, "0")).join("")))
#
# then paste the printed hex string below.
password_hash: ""
# Second, separate password gating just the hub's open-trial editors
# (add/edit/remove on Sessions, Quests, Lore, NPCs, Locations, Misc.) —
# the page itself stays viewable per password_hash above regardless of
# this. Leave blank to skip this gate entirely — editing stays wide open,
# no password prompt at all (this is the default for existing campaigns).
# Generate the hash the same way as password_hash above. Setting this
# alone does nothing server-side — the campaign's slug must also be added
# to worker/ddb-character-proxy.js's EDIT_LOCKED_SLUGS, and the Worker's
# EDIT_SECRET env var must be set to this same plaintext password.
edit_password_hash: ""
---
