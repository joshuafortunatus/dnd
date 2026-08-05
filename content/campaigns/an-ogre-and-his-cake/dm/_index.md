---
title: "DM Portal"
date: 2026-08-05
layout: "dm-portal"
# Gates this page behind a client-side password prompt (obscurity, not real
# security — the gated content still ships in the page's HTML, so anyone
# using view-source or disabling JS can read it regardless of the password).
# Leave blank to skip the gate entirely — the portal renders wide open, no
# password prompt at all. Fine for local dev; set a real password before
# relying on this for anything you don't want a random visitor stumbling
# onto (it's still just obscurity, not real security, once set).
#
# To generate a hash, open a browser console (any page) and run:
#
#   crypto.subtle.digest("SHA-256", new TextEncoder().encode("your-password"))
#     .then(b => console.log(Array.from(new Uint8Array(b))
#       .map(x => x.toString(16).padStart(2, "0")).join("")))
#
# then paste the printed hex string below.
password_hash: "aebbe5323db1fba558e9c4fd8d30aee3124da1c03de4301bbec938b846eaf7ec"
---

