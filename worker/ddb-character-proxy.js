/**
 * Cloudflare Worker, two jobs:
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
 * Deploy: Cloudflare dashboard → Workers & Pages → this Worker → paste this
 * file's contents in place of the existing code → Deploy. Additionally, to
 * enable sync (job 2):
 *   - Workers & Pages → KV → Create a namespace (any name, e.g. "portal-data").
 *   - This Worker → Settings → Variables → KV Namespace Bindings → Add
 *     binding → variable name `PORTAL_DATA`, pointing at that namespace.
 *   - This Worker → Settings → Variables → Environment Variables → Add
 *     variable → name `SYNC_SECRET`, type **Secret** (not plain text) →
 *     set it to the SAME plaintext password you used to generate
 *     password_hash for the DM portal page. This is never committed to
 *     git. Nothing further to configure client-side — logging into the DM
 *     portal on any device is what enables sync on that device.
 *
 * Usage:
 *   GET  /character/<numeric id>          — D&D Beyond character proxy (no auth)
 *   GET  /sync/<slug>/<key>                — read a stored JSON blob (Authorization: Bearer <SYNC_SECRET>)
 *   PUT  /sync/<slug>/<key>  (JSON body)   — write a stored JSON blob (Authorization: Bearer <SYNC_SECRET>)
 *   <slug> is a campaign slug; <key> is one of: characters, expectations, travel-plans, npcs
 */

const ALLOWED_ORIGIN = "https://joshuafortunatus.github.io";
const ALLOWED_SYNC_KEYS = ["characters", "expectations", "travel-plans", "npcs"];

function corsHeaders(extra) {
  return Object.assign(
    {
      "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
      "Access-Control-Allow-Methods": "GET, PUT, OPTIONS",
      "Access-Control-Allow-Headers": "Authorization, Content-Type",
    },
    extra || {}
  );
}

function authorized(request, env) {
  const auth = request.headers.get("Authorization") || "";
  return Boolean(env.SYNC_SECRET) && auth === "Bearer " + env.SYNC_SECRET;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders() });
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
        headers: corsHeaders({ "Content-Type": "application/json" }),
      });
    }

    const syncMatch = url.pathname.match(/^\/sync\/([a-z0-9-]+)\/([a-z0-9-]+)$/);
    if (syncMatch) {
      const slug = syncMatch[1];
      const key = syncMatch[2];

      if (!ALLOWED_SYNC_KEYS.includes(key)) {
        return new Response("Unknown sync key.", { status: 404, headers: corsHeaders() });
      }
      if (!authorized(request, env)) {
        return new Response("Unauthorized.", { status: 401, headers: corsHeaders() });
      }
      if (!env.PORTAL_DATA) {
        return new Response("PORTAL_DATA KV binding is not configured on this Worker.", {
          status: 500,
          headers: corsHeaders(),
        });
      }

      const storageKey = slug + ":" + key;

      if (request.method === "GET") {
        const stored = await env.PORTAL_DATA.get(storageKey);
        return new Response(stored || "null", {
          status: 200,
          headers: corsHeaders({ "Content-Type": "application/json" }),
        });
      }

      if (request.method === "PUT") {
        const body = await request.text();
        try {
          JSON.parse(body);
        } catch (e) {
          return new Response("Body must be valid JSON.", { status: 400, headers: corsHeaders() });
        }
        await env.PORTAL_DATA.put(storageKey, body);
        return new Response("OK", { status: 200, headers: corsHeaders() });
      }

      return new Response("Method not allowed.", { status: 405, headers: corsHeaders() });
    }

    return new Response("Not found. Use /character/<numeric id> or /sync/<slug>/<key>.", {
      status: 404,
      headers: corsHeaders(),
    });
  },
};
