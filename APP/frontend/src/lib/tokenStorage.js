// Single source of truth for auth token persistence.
//
// Historically the token was written to sessionStorage in some places and read
// from localStorage in others, which silently broke authenticated requests.
// Centralizing access here guarantees every read/write uses the same store.
//
// localStorage is intentional: the token must survive a full app restart, which
// matters for the mobile (Capacitor) builds where the webview is torn down and
// recreated between launches.

const TOKEN_KEY = "ides_token";

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Storage can throw in private-mode / restricted webviews; fail soft.
  }
}

export function clearToken() {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // no-op
  }
}
