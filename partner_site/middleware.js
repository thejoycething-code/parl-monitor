// Shared-passphrase gate (fail closed: no env var, no access).
export const config = { matcher: ["/((?!favicon.ico).*)"] };

export default function middleware(request) {
  const phrase = process.env.PARTNER_PASSPHRASE;
  const auth = request.headers.get("authorization") || "";
  if (phrase && auth === "Basic " + btoa("partners:" + phrase)) {
    return; // authenticated: serve the static page
  }
  return new Response("Authentication required.", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="Parliamentary Monitor"' },
  });
}
