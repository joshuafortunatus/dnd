---
title: "DM Portal"
date: 2026-07-24
layout: "dm-portal"
# Gates this page behind a client-side password prompt (obscurity, not real
# security — the gated content still ships in the page's HTML, so anyone
# using view-source or disabling JS can read it regardless of the password).
# Leave blank to disable the gate entirely (shows a "no password set" notice
# instead of the prompt).
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

## Session Zero

