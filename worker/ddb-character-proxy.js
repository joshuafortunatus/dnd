/**
 * Cloudflare Worker: CORS proxy for D&D Beyond's public character JSON
 * endpoint, so the DM portal (a static site with no backend of its own) can
 * fetch a character live when a DM pastes a link and hits submit.
 *
 * D&D Beyond's endpoint requires no credentials — it just blocks direct
 * browser calls via CORS. This Worker holds no secrets; it only forwards a
 * GET for a numeric character id to a hardcoded upstream URL. The id is
 * validated against \d+ before use so this can't be abused as an open proxy
 * to arbitrary URLs.
 *
 * Deploy: Cloudflare dashboard → Workers & Pages → Create application →
 * Create Worker → paste this file's contents in place of the default →
 * Deploy. Note the resulting *.workers.dev URL.
 *
 * Usage: GET https://<your-worker>.workers.dev/character/<id>
 */

const ALLOWED_ORIGIN = "https://joshuafortunatus.github.io";

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const match = url.pathname.match(/^\/character\/(\d+)$/);

    if (!match) {
      return new Response("Not found. Use /character/<numeric id>.", { status: 404 });
    }

    const characterId = match[1];
    const upstream = await fetch(
      `https://character-service.dndbeyond.com/character/v5/character/${characterId}`
    );
    const body = await upstream.text();

    return new Response(body, {
      status: upstream.status,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
      },
    });
  },
};
