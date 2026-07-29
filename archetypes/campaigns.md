---
title: "{{ replace .File.ContentBaseName "-" " " | title }}"
date: {{ .Date }}
layout: "hub"
system: "D&D 5e"
status: "active"
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
---
