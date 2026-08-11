import axios from "axios";
import { getToken } from "./tokenStorage";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL;

if (!BACKEND_URL) {
  console.error(
    "[api] VITE_BACKEND_URL is not set. " +
    "Add it to your Vercel environment variables and redeploy."
  );
}

export const API = `${(BACKEND_URL || "").replace(/\/+$/, "")}/api`;

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((cfg) => {
  const t = getToken();
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

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
