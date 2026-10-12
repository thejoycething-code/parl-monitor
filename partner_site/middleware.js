// Password-only gate: one box, no username (Christopher, 2026-08-05).
// Fails closed -- no PARTNER_PASSPHRASE env var, no access.
export const config = { matcher: ["/((?!favicon.ico).*)"] };

const FORM = (retry) => `<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Parliamentary Monitor</title>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
<style>
body { font: 15px/1.6 Roboto, sans-serif; color:#52575C; display:flex; min-height:90vh;
       align-items:center; justify-content:center; margin:0; padding:1rem; }
.card { border:1px solid #EEEEEE; border-radius:8px; padding:2rem; max-width:24rem; width:100%; }
h1 { font-size:1.15rem; color:#52575C; border-bottom:4px solid #4285f4;
     padding-bottom:.4rem; margin:0 0 .3rem; }
p { font-size:.9em; }
input { width:100%; padding:.6rem; font:inherit; border:1px solid #C8D0DC;
        border-radius:4px; box-sizing:border-box; }
button { margin-top:.7rem; width:100%; padding:.6rem; font:inherit; font-weight:700;
         background:#4285f4; color:#FFF; border:0; border-radius:4px; cursor:pointer; }
.err { color:#DB544F; font-size:.86em; font-weight:700; }
</style></head><body>
<div class="card">
<h1>Parliamentary Monitor</h1>
<p>Coalition partner edition, prepared by CitizenGO UK. Please enter the password you were given.</p>
${retry ? '<p class="err">That password was not recognised.</p>' : ''}
<form method="POST">
<input type="password" name="password" placeholder="Password" autofocus autocomplete="current-password">
<button type="submit">Open the briefing</button>
</form>
</div></body></html>`;

export default async function middleware(request) {
  const phrase = process.env.PARTNER_PASSPHRASE;
  if (!phrase) {
    return new Response("Access is not configured.", { status: 503 });
  }
  const cookie = request.headers.get("cookie") || "";
  if (cookie.split(/;\s*/).includes("pm_access=" + encodeURIComponent(phrase))) {
    return; // already unlocked: serve the static page
  }
  if (request.method === "POST") {
    const body = await request.formData().catch(() => null);
    if (body && body.get("password") === phrase) {
      return new Response(null, {
        status: 303,
        headers: {
          location: new URL(request.url).pathname,
          "set-cookie": "pm_access=" + encodeURIComponent(phrase) +
            "; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=7776000",
        },
      });
    }
    return new Response(FORM(true), {
      status: 401, headers: { "content-type": "text/html; charset=utf-8" },
    });
  }
  return new Response(FORM(false), {
    status: 401, headers: { "content-type": "text/html; charset=utf-8" },
  });
}
