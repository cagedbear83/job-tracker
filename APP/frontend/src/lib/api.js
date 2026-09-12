import axios from "axios";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL;

if (!BACKEND_URL) {
  console.error(
    "[api] VITE_BACKEND_URL is not set. " +
    "Add it to your Vercel environment variables and redeploy."
  );
}

export const API = `${(BACKEND_URL || "").replace(/\/+$/, "")}/api`;

// No withCredentials: there is no refresh cookie any more. Clerk mints
// short-lived session tokens on the client and we send them as a bearer
// header, which keeps this API free of any cookie-based CSRF surface.
export const api = axios.create({ baseURL: API });

// Bridge from Clerk's React-only session into this plain module.
//
// Clerk exposes getToken() through the useAuth() hook, but axios lives
// outside React. ClerkTokenBridge (see components/ClerkTokenBridge.jsx)
// registers the live getter once the provider has mounted; until then this
// returns null and requests go out unauthenticated, which is correct — there
// is no session yet.
let tokenGetter = async () => null;

export function setTokenGetter(fn) {
  tokenGetter = fn || (async () => null);
}

// Returns a valid session token, or null when signed out. Clerk handles
// caching and refresh internally, so callers can ask on every request.
// Exported for the call sites that build a raw fetch() themselves instead of
// going through `api` — PDF/CSV downloads in WeekDetail.jsx, Documents.jsx
// and BenefitWeeks.jsx bypass the interceptor below.
export async function getValidToken() {
  try {
    return await tokenGetter();
  } catch {
    return null;
  }
}

// Attach the current Clerk session token. Clerk refreshes it under the hood,
// so there is no expiry check or refresh race to manage here any more.
api.interceptors.request.use(async (cfg) => {
  const t = await getValidToken();
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

// A 401 now means the Clerk session is genuinely gone (signed out in another
// tab, session revoked in the dashboard). There is nothing to retry — Clerk
// already refreshes tokens transparently — so surface it and let
// <SignedOut> redirect.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      window.dispatchEvent(new CustomEvent("session-expired"));
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

// Maps an axios error to a human-readable string suitable for display in a
// toast or inline error. Covers the most common failure modes so users see
// something actionable rather than a raw axios message like "Network Error"
// or "Request failed with status code 504".
export function formatApiError(err) {
  const status = err?.response?.status;
  const d = err?.response?.data?.detail;

  // Gateway / server errors — the backend may be healthy but slow, restarting,
  // or overloaded. Give the user enough context to self-triage or include in a
  // support message without exposing internal infrastructure details.
  if (status === 504) {
    return "The server took too long to respond (Error 504). Please try again in a moment — if this keeps happening, contact support and mention Error 504.";
  }
  if (status === 502) {
    return "The server is temporarily unavailable (Error 502). Please try again shortly — if the problem persists, contact support and mention Error 502.";
  }
  if (status === 503) {
    return "The service is temporarily unavailable (Error 503). Please try again in a moment — if the problem persists, contact support and mention Error 503.";
  }
  if (status === 500) {
    const msg = typeof d === "string" ? d : null;
    return msg
      ? `${msg} (Error 500)`
      : "Something went wrong on our end (Error 500). Please try again — if this continues, contact support and mention Error 500.";
  }

  // Backend sent a structured detail message — use it directly.
  if (d != null) {
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return d.map((e) => e?.msg || JSON.stringify(e)).join(" ");
    if (typeof d?.msg === "string") return d.msg;
    return JSON.stringify(d);
  }

  // axios "Network Error" means the request never reached the server — no
  // internet, DNS failure, CORS preflight blocked, server completely unreachable.
  if (!err?.response && err?.message === "Network Error") {
    return "Unable to reach the server. Check your internet connection and try again — if the problem continues, contact support and mention \"Network Error\".";
  }

  return err?.message || "Something went wrong. Please try again.";
}
