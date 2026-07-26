/**
 * Cloudflare Worker, four jobs:
 *
 * 1) CORS proxy for D&D Beyond's public character JSON endpoint, so the DM
 *    portal (a static site with no backend of its own) can fetch a
 *    character live when a DM pastes a link and hits submit. D&D Beyond's
 *    endpoint requires no credentials — it just blocks direct browser calls
 *    via CORS. This part holds no secrets; it only forwards a GET for a
 *    numeric character id to a hardcoded upstream URL.
 *
 * 2) A small KV-backed sync store so DM portal data (Character Importer's
 *    imported roster, Game Expectations edits, Travel Planner plans) can
 *    follow a DM across devices instead of being stuck in one browser's
 *    localStorage. Since this repo is public (hugo.toml's ddb_proxy_url
 *    gives away this Worker's URL to anyone reading the source), the sync
 *    endpoints require a shared secret — otherwise anyone who found the URL
 *    could read or overwrite this data.
 *
 * 3) CORS proxy for aidedd.org monster stat block pages, so the NPC
 *    Tracker's Monster Manual field can fetch and render a full stat block
 *    live the moment a DM picks a monster, instead of only linking out.
 *    Nothing from aidedd.org is stored anywhere (not in KV, not in this
 *    repo) — this just forwards a GET for one of $monsters' existing links
 *    (data/monsters.json) so the browser can read it despite aidedd.org
 *    not sending CORS headers of its own. Restricted to that one host and
 *    to the two URL shapes aidedd.org actually uses for monster pages, so
 *    this can't be turned into an open proxy for arbitrary URLs.
 *
 * 4) R2-backed file storage for the DM portal's File Library section
 *    (maps, module PDFs, misc. files, reference material). Metadata (name,
 *    category, upload date, sentToPlayers flag, content type, size) is
 *    small and reuses job 2's KV sync store as-is (key "files", added to
 *    ALLOWED_SYNC_KEYS below) — no new server code needed for that part.
 *    But actual file bytes do NOT go into that same KV blob: the existing
 *    sync design stores each key's entire list as one JSON value, capped
 *    at 25MB by KV, and base64-encoding file bytes into that blob (on top
 *    of documents being in scope, not just images) would hit that ceiling
 *    fast. R2 has no such per-object ceiling, so file bytes live there
 *    instead, addressed by the same id as their KV metadata record.
 *
 *    There's no separate sync passphrase to invent or type in anywhere:
 *    the DM portal page's own password (whatever you set password_hash to,
 *    in the campaign's dm/_index.md front matter) doubles as the sync
 *    credential. The moment someone types the correct portal password on a
 *    given browser, that password is saved there and used as the sync
 *    token automatically going forward on that device — no extra step.
 *    This means SYNC_SECRET below must be set to the exact same plaintext
 *    password whose hash you put in password_hash — not an independent
 *    value.
 *
 * Deploy: two working paths, pick either.
 *
 *   CLI (verified working, no dashboard clicking): from this worker/
 *   directory, `npx wrangler login` once (opens a browser to authorize —
 *   this step alone can't be scripted around, it needs your real Cloudflare
 *   session). After that, `npx wrangler r2 bucket create <bucket_name>`
 *   (matching worker/wrangler.toml's r2_buckets.bucket_name) creates the
 *   File Library bucket, and `npx wrangler deploy` pushes this file's code
 *   and applies both the KV and R2 bindings declared in wrangler.toml in
 *   one shot. R2 must be enabled once on the account first (Cloudflare
 *   dashboard → R2 → follow its one-time enablement prompt; this part
 *   can't be done via API either). SYNC_SECRET (below) still needs
 *   `npx wrangler secret put SYNC_SECRET` (or the dashboard, either works)
 *   since secrets are deliberately kept out of wrangler.toml.
 *
 *   Dashboard (no CLI/terminal needed): Workers & Pages → this Worker →
 *   paste this file's contents in place of the existing code → Deploy.
 *   Additionally, to enable sync (job 2):
 *   - Workers & Pages → KV → Create a namespace (any name, e.g. "portal-data").
 *   - This Worker → Settings → Variables → KV Namespace Bindings → Add
 *     binding → variable name `PORTAL_DATA`, pointing at that namespace.
 *   - This Worker → Settings → Variables → Environment Variables → Add
 *     variable → name `SYNC_SECRET`, type **Secret** (not plain text) →
 *     set it to the SAME plaintext password you used to generate
 *     password_hash for the DM portal page. This is never committed to
 *     git. Nothing further to configure client-side — logging into the DM
 *     portal on any device is what enables sync on that device.
 *   And, to enable File Library (job 4):
 *   - Workers & Pages → R2 → Create a bucket (any name, e.g. "dnd-portal-files").
 *   - This Worker → Settings → Variables → R2 Bucket Bindings → Add
 *     binding → variable name `PORTAL_FILES`, pointing at that bucket.
 *   - No new secret needed — SYNC_SECRET (above) already gates File
 *     Library writes/deletes too.
 *
 * Usage:
 *   GET  /character/<numeric id>          — D&D Beyond character proxy (no auth)
 *   GET  /sync/<slug>/<key>                — read a stored JSON blob (Authorization: Bearer <SYNC_SECRET>,
 *                                             EXCEPT key=characters, which is a public read — the
 *                                             campaign hub page's Characters tab fetches it directly,
 *                                             unauthenticated, so any visitor can see the roster)
 *   PUT  /sync/<slug>/<key>  (JSON body)   — write a stored JSON blob (Authorization: Bearer <SYNC_SECRET>,
 *                                             always required, including for key=characters)
 *   <slug> is a campaign slug; <key> is one of: characters, pc-manager,
 *     travel-plans, npcs, settlements, journal, conflicts, magic-items,
 *     bastions, files
 *   GET  /monster?url=<aidedd.org monster page URL>  — aidedd.org proxy (no auth), url must be
 *                                             https://www.aidedd.org/monster/<slug> (2024) or
 *                                             https://www.aidedd.org/dnd/monstres.php?vo=<slug> (2014)
 *   PUT    /files/<slug>/<fileId>          — upload file bytes to R2 (Authorization required always).
 *                                             Body is the raw file; Content-Type and X-File-Name headers
 *                                             carry the file's type and original filename.
 *   DELETE /files/<slug>/<fileId>          — delete file bytes from R2 (Authorization required always)
 *   GET    /files/<slug>/<fileId>          — read file bytes from R2. Authorization bypasses the check
 *                                             below entirely (DM-side preview, including drafts not yet
 *                                             sent to players). Without it, public ONLY if this file's
 *                                             metadata record (KV key <slug>:files) has sentToPlayers
 *                                             true — decided per-record, mirroring the /sync "characters"
 *                                             public-read exception above but at file granularity instead
 *                                             of key granularity, since an unsent file's very name can be
 *                                             a spoiler.
 *   GET    /public-files/<slug>            — public, no auth: <slug>:files KV metadata filtered to
 *                                             sentToPlayers=true entries only. Exists as its own route
 *                                             rather than making the whole "files" sync key publicly
 *                                             readable (like "characters" is), specifically so an
 *                                             unauthenticated caller never sees draft/unsent file metadata.
 */

/* localhost:1313 is Hugo's default `hugo server -D` port (see README) —
 * included so this Worker is testable locally, not just against the
 * deployed GitHub Pages origin. The first entry is the fallback used when
 * the request's Origin doesn't match either (e.g. no Origin header at
 * all, as with a direct curl). */
const ALLOWED_ORIGINS = ["https://joshuafortunatus.github.io", "http://localhost:1313"];
const ALLOWED_SYNC_KEYS = [
  "characters", "pc-manager", "travel-plans", "npcs", "settlements",
  "journal", "conflicts", "magic-items", "bastions", "files",
];

/* Sanity default, not a hard platform fact — Workers' request body size
 * ceiling can change by plan tier; re-check current Cloudflare docs before
 * relying on this if it ever needs to grow. Comfortably above a realistic
 * map image or module PDF. */
const MAX_FILE_BYTES = 15 * 1024 * 1024;

function corsHeaders(request, extra) {
  const origin = request.headers.get("Origin") || "";
  const allowOrigin = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return Object.assign(
    {
      "Access-Control-Allow-Origin": allowOrigin,
      "Access-Control-Allow-Methods": "GET, PUT, DELETE, OPTIONS",
      "Access-Control-Allow-Headers": "Authorization, Content-Type, X-File-Name",
    },
    extra || {}
  );
}

function authorized(request, env) {
  const auth = request.headers.get("Authorization") || "";
  return Boolean(env.SYNC_SECRET) && auth === "Bearer " + env.SYNC_SECRET;
}

const ALLOWED_MONSTER_URL = /^https:\/\/www\.aidedd\.org\/(monster\/[a-z0-9-]+|dnd\/monstres\.php\?vo=[a-z0-9-]+)$/i;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders(request) });
    }

    if (url.pathname === "/monster") {
      const target = url.searchParams.get("url") || "";
      if (!ALLOWED_MONSTER_URL.test(target)) {
        return new Response("url must be an aidedd.org monster page.", { status: 400, headers: corsHeaders(request) });
      }
      const upstream = await fetch(target, { headers: { "User-Agent": "Mozilla/5.0" } });
      const body = await upstream.text();
      return new Response(body, {
        status: upstream.status,
        headers: corsHeaders(request, { "Content-Type": "text/html; charset=utf-8" }),
      });
    }

    const characterMatch = url.pathname.match(/^\/character\/(\d+)$/);
    if (characterMatch) {
      const characterId = characterMatch[1];
      const upstream = await fetch(
        `https://character-service.dndbeyond.com/character/v5/character/${characterId}`
      );
      const body = await upstream.text();
      return new Response(body, {
        status: upstream.status,
        headers: corsHeaders(request, { "Content-Type": "application/json" }),
      });
    }

    const syncMatch = url.pathname.match(/^\/sync\/([a-z0-9-]+)\/([a-z0-9-]+)$/);
    if (syncMatch) {
      const slug = syncMatch[1];
      const key = syncMatch[2];

      if (!ALLOWED_SYNC_KEYS.includes(key)) {
        return new Response("Unknown sync key.", { status: 404, headers: corsHeaders(request) });
      }
      // The character roster is the one exception to auth-required reads —
      // the public campaign hub page displays it (name/class/level/species
      // only, no DM notes) to any visitor, not just the DM. Writes still
      // always require the secret.
      const isPublicRosterRead = key === "characters" && request.method === "GET";
      if (!isPublicRosterRead && !authorized(request, env)) {
        return new Response("Unauthorized.", { status: 401, headers: corsHeaders(request) });
      }
      if (!env.PORTAL_DATA) {
        return new Response("PORTAL_DATA KV binding is not configured on this Worker.", {
          status: 500,
          headers: corsHeaders(request),
        });
      }

      const storageKey = slug + ":" + key;

      if (request.method === "GET") {
        const stored = await env.PORTAL_DATA.get(storageKey);
        return new Response(stored || "null", {
          status: 200,
          headers: corsHeaders(request, { "Content-Type": "application/json" }),
        });
      }

      if (request.method === "PUT") {
        const body = await request.text();
        try {
          JSON.parse(body);
        } catch (e) {
          return new Response("Body must be valid JSON.", { status: 400, headers: corsHeaders(request) });
        }
        await env.PORTAL_DATA.put(storageKey, body);
        return new Response("OK", { status: 200, headers: corsHeaders(request) });
      }

      return new Response("Method not allowed.", { status: 405, headers: corsHeaders(request) });
    }

    const fileMatch = url.pathname.match(/^\/files\/([a-z0-9-]+)\/([a-z0-9]+)$/);
    if (fileMatch) {
      const slug = fileMatch[1];
      const fileId = fileMatch[2];

      if (!env.PORTAL_FILES) {
        return new Response("PORTAL_FILES R2 binding is not configured on this Worker.", {
          status: 500,
          headers: corsHeaders(request),
        });
      }

      const objectKey = slug + "/" + fileId;

      if (request.method === "PUT") {
        if (!authorized(request, env)) {
          return new Response("Unauthorized.", { status: 401, headers: corsHeaders(request) });
        }
        const contentLength = Number(request.headers.get("Content-Length") || "0");
        if (contentLength > MAX_FILE_BYTES) {
          return new Response("File is too large (max " + MAX_FILE_BYTES + " bytes).", {
            status: 413,
            headers: corsHeaders(request),
          });
        }
        const contentType = request.headers.get("Content-Type") || "application/octet-stream";
        const fileName = decodeURIComponent(request.headers.get("X-File-Name") || "file");
        await env.PORTAL_FILES.put(objectKey, request.body, {
          httpMetadata: { contentType },
          customMetadata: { fileName },
        });
        return new Response("OK", { status: 200, headers: corsHeaders(request) });
      }

      if (request.method === "DELETE") {
        if (!authorized(request, env)) {
          return new Response("Unauthorized.", { status: 401, headers: corsHeaders(request) });
        }
        await env.PORTAL_FILES.delete(objectKey);
        return new Response("OK", { status: 200, headers: corsHeaders(request) });
      }

      if (request.method === "GET") {
        if (!authorized(request, env)) {
          if (!env.PORTAL_DATA) {
            return new Response("PORTAL_DATA KV binding is not configured on this Worker.", {
              status: 500,
              headers: corsHeaders(request),
            });
          }
          const stored = await env.PORTAL_DATA.get(slug + ":files");
          let records = [];
          try {
            records = JSON.parse(stored || "[]") || [];
          } catch (e) {
            records = [];
          }
          const record = records.filter((r) => r.id === fileId)[0];
          if (!record || !record.sentToPlayers) {
            return new Response("Unauthorized.", { status: 401, headers: corsHeaders(request) });
          }
        }

        const object = await env.PORTAL_FILES.get(objectKey);
        if (!object) {
          return new Response("Not found.", { status: 404, headers: corsHeaders(request) });
        }
        const contentType = (object.httpMetadata && object.httpMetadata.contentType) || "application/octet-stream";
        const responseHeaders = corsHeaders(request, { "Content-Type": contentType });
        if (!contentType.startsWith("image/")) {
          const fileName = (object.customMetadata && object.customMetadata.fileName) || "file";
          responseHeaders["Content-Disposition"] = 'attachment; filename="' + fileName + '"';
        }
        return new Response(object.body, { status: 200, headers: responseHeaders });
      }

      return new Response("Method not allowed.", { status: 405, headers: corsHeaders(request) });
    }

    const publicFilesMatch = url.pathname.match(/^\/public-files\/([a-z0-9-]+)$/);
    if (publicFilesMatch) {
      const slug = publicFilesMatch[1];
      if (!env.PORTAL_DATA) {
        return new Response("PORTAL_DATA KV binding is not configured on this Worker.", {
          status: 500,
          headers: corsHeaders(request),
        });
      }
      const stored = await env.PORTAL_DATA.get(slug + ":files");
      let records = [];
      try {
        records = JSON.parse(stored || "[]") || [];
      } catch (e) {
        records = [];
      }
      const publicRecords = records.filter((r) => r.sentToPlayers);
      return new Response(JSON.stringify(publicRecords), {
        status: 200,
        headers: corsHeaders(request, { "Content-Type": "application/json" }),
      });
    }

    return new Response(
      "Not found. Use /character/<numeric id>, /sync/<slug>/<key>, /files/<slug>/<fileId>, /public-files/<slug>, or /monster?url=<aidedd.org URL>.",
      { status: 404, headers: corsHeaders(request) }
    );
  },
};
