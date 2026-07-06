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
---
