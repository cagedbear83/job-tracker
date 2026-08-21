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

export function formatApiError(err) {
  const d = err?.response?.data?.detail;
  if (d == null) return err?.message || "Something went wrong";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((e) => e?.msg || JSON.stringify(e)).join(" ");
  if (typeof d?.msg === "string") return d.msg;
  return JSON.stringify(d);
}
