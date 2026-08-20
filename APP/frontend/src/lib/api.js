import axios from "axios";
import { getToken, setToken, clearToken, isTokenExpired } from "./tokenStorage";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL;

if (!BACKEND_URL) {
  console.error(
    "[api] VITE_BACKEND_URL is not set. " +
    "Add it to your Vercel environment variables and redeploy."
  );
}

export const API = `${(BACKEND_URL || "").replace(/\/+$/, "")}/api`;

// withCredentials so the httpOnly refresh-token cookie (scoped to
// /api/auth/*, see backend core.py) is sent on the auth endpoints that need
// it. It's a no-op for every other endpoint since the browser only attaches
// a cookie to requests whose path matches the cookie's Path attribute.
export const api = axios.create({ baseURL: API, withCredentials: true });

function isAuthBootstrapUrl(url) {
  const u = url || "";
  return u.includes("/auth/refresh") || u.includes("/auth/login") || u.includes("/auth/register");
}

// Exchanges the refresh-token cookie for a new short-lived access token.
// Concurrent callers share one in-flight request rather than each firing
// their own refresh (which would race the token-rotation on the backend).
let refreshPromise = null;
export function refreshSession() {
  if (!refreshPromise) {
    refreshPromise = api
      .post("/auth/refresh")
      .then((r) => {
        setToken(r.data.token);
        return r.data.token;
      })
      .catch(() => {
        clearToken();
        return null;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

// Returns a token guaranteed not to be expired (refreshing first if needed),
// or null if there's no valid session. For call sites that build a raw
// `fetch()` request themselves instead of going through `api` (PDF/CSV
// downloads — see WeekDetail.jsx, Documents.jsx, BenefitWeeks.jsx), since
// those bypass the request interceptor below.
export async function getValidToken() {
  const t = getToken();
  if (t && !isTokenExpired(t)) return t;
  return refreshSession();
}

// Proactively refresh before a request goes out with a token that's already
// (or about to be) expired, rather than waiting to get a 401 back.
api.interceptors.request.use(async (cfg) => {
  let t = getToken();
  if (!isAuthBootstrapUrl(cfg.url) && (!t || isTokenExpired(t))) {
    t = await refreshSession();
  }
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

// Reactive fallback: if a request still comes back 401 (clock skew, a token
// invalidated server-side mid-flight, etc.), try one silent refresh-and-retry
// before giving up. Registered first so it sees the raw error before the
// interceptors below.
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const cfg = error.config;
    if (
      error.response?.status === 401 &&
      cfg &&
      !cfg._retriedAfterRefresh &&
      !isAuthBootstrapUrl(cfg.url)
    ) {
      cfg._retriedAfterRefresh = true;
      const t = await refreshSession();
      if (t) {
        cfg.headers = { ...cfg.headers, Authorization: `Bearer ${t}` };
        return api(cfg);
      }
    }
    return Promise.reject(error);
  }
);

api.interceptors.response.use(
     (response) => response,
     (error) => {
       if (error.response?.status === 402) {
         window.dispatchEvent(
           new CustomEvent("upgrade-required", { detail: error.response.data?.detail })
         );
       }
       return Promise.reject(error);
     }
   );

// Guard: if Vercel's catch-all rewrite returns the SPA HTML instead of JSON
// (happens when VITE_BACKEND_URL is wrong/missing), treat it as an error so
// components' catch blocks fire instead of receiving an HTML string as data.
api.interceptors.response.use(
  (response) => {
    if (
      typeof response.data === "string" &&
      response.data.trimStart().startsWith("<")
    ) {
      return Promise.reject(
        new Error("API returned HTML — check VITE_BACKEND_URL in Vercel settings.")
      );
    }
    return response;
  },
  (error) => Promise.reject(error)
);

export function formatApiError(err) {
  const d = err?.response?.data?.detail;
  if (d == null) return err?.message || "Something went wrong";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((e) => e?.msg || JSON.stringify(e)).join(" ");
  if (typeof d?.msg === "string") return d.msg;
  return JSON.stringify(d);
}
