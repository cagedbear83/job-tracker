// Single source of truth for the access token — held in memory ONLY.
//
// This used to live in localStorage, which meant the token (valid for 7
// days) survived closing the browser entirely and was readable by any
// script on the page for its full lifetime. Now:
//   - The access token lives only in a JS module variable — it vanishes on
//     tab close/refresh and is not written to any Storage API, so an XSS
//     payload can only ever grab whatever few minutes are left on it.
//   - Long-lived session state lives server-side, in a rotating refresh
//     token delivered as an httpOnly cookie (see lib/api.js's refreshSession)
//     that JS can never read at all, XSS included.
//   - On a fresh page load there's no in-memory token yet — AuthProvider
//     calls refreshSession() to silently re-establish one from the cookie,
//     if a valid one exists.
//
// This is a web-only app (no native/Capacitor build exists in this repo).

let accessToken = null;

export function getToken() {
  return accessToken;
}

export function setToken(token) {
  accessToken = token || null;
}

export function clearToken() {
  accessToken = null;
}

// Decodes a JWT's payload without verifying the signature (verification is
// the backend's job) — used client-side purely to decide whether it's worth
// sending a request with the current token or refreshing first.
export function isTokenExpired(token) {
  if (!token) return true;
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return true;
    const payload = JSON.parse(atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")));
    const exp = payload.exp;
    if (!exp) return false;
    // Treat a token as "expired" a little early (30s skew buffer) so a
    // request doesn't leave with a token that dies in transit.
    return Date.now() >= exp * 1000 - 30_000;
  } catch {
    return true;
  }
}
