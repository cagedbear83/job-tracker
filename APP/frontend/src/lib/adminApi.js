// src/lib/adminApi.js
// Typed client for the /api/admin/platform backend surface. Sensitive
// endpoints take a step_up_password in the body — never store it, pass
// through.
//
// ADAPTED from admin_portal/adminApi.js:
//   - BASE changed from `/api/admin` to `/api/admin/platform` to match how
//     the backend integration namespaced these routes (see
//     routers/admin_platform_compliance.py's docstring in the backend repo
//     for why: /api/admin/users etc. already exist with a different shape
//     and are covered by the existing test suite, so the new admin_portal
//     endpoints were mounted one level deeper instead of overwriting them).
//   - The `case_worker` tier value in this file's callers (see
//     AdminPlatform.jsx) was corrected to `caseworker` to match this
//     backend's actual subscription.Tier enum (Tier.CASEWORKER = "caseworker").
//   - Disputes methods below are now backed by routers/admin_disputes.py
//     (built fresh — the original admin_portal never shipped it, it only
//     referenced it). Endpoint shapes are unchanged. Note: the dispute list
//     is fed by Stripe webhook events (charge.dispute.created/updated) — it
//     will legitimately be empty until a real dispute occurs.
//   - SWAPPED transport: the original used raw `fetch(..., { credentials:
//     "include" })`, assuming cookie-based sessions. This app authenticates
//     with a JWT bearer token (see src/lib/tokenStorage.js) attached by an
//     axios request interceptor in src/lib/api.js — every other page in
//     this codebase calls the backend through that shared `api` instance.
//     Using raw fetch here would have sent every admin-platform request
//     with no Authorization header, so every call would 401. Rewritten to
//     reuse `api` (and its existing 402/HTML-response interceptors) instead
//     of introducing a second, differently-authenticated HTTP client.

import { api, formatApiError } from "@/lib/api";

const BASE = "/admin/platform"; // api's baseURL already includes /api

async function req(path, { method = "GET", body } = {}) {
  try {
    const { data } = await api.request({
      url: `${BASE}${path}`,
      method,
      data: body,
    });
    return data;
  } catch (e) {
    const err = new Error(formatApiError(e));
    err.status = e?.response?.status;
    throw err;
  }
}

export const adminApi = {
  // Users
  listUsers: (q = "", skip = 0, limit = 25) =>
    req(`/users?${new URLSearchParams({ q, skip, limit })}`),
  getUser: (id) => req(`/users/${encodeURIComponent(id)}`),
  getUserPii: (id, ticketId) =>
    req(`/users/${encodeURIComponent(id)}/pii${ticketId ? `?ticket_id=${encodeURIComponent(ticketId)}` : ""}`),

  // Subscriptions
  getSubscription: (id) => req(`/subscriptions/${encodeURIComponent(id)}`),

  // Comps (admin + step-up)
  compStatus: () => req(`/comps/status`),
  grantComp: (payload) => req(`/comps/grant`, { method: "POST", body: payload }),
  revokeComp: (payload) => req(`/comps/revoke`, { method: "POST", body: payload }),

  // Refunds
  listRefunds: (statusFilter) =>
    req(`/refunds${statusFilter ? `?status_filter=${statusFilter}` : ""}`),
  createRefund: (payload) => req(`/refunds`, { method: "POST", body: payload }),
  approveRefund: (id, payload) =>
    req(`/refunds/${id}/approve`, { method: "POST", body: payload }),
  markRefundExecuted: (id) =>
    req(`/refunds/${id}/mark-executed`, { method: "POST" }),

  // System + compliance
  systemHealth: () => req(`/system/health`),
  auditSearch: (params) =>
    req(`/compliance/audit?${new URLSearchParams(params)}`),
  retention: (withinDays = 14) =>
    req(`/compliance/retention?within_days=${withinDays}`),

  // Disputes — NOT wired up on the backend in this integration. See the
  // module comment above. Left here only so the shape is documented for
  // whoever builds the disputes admin router later.
  listDisputes: () => req(`/disputes`),
  getDispute: (id) => req(`/disputes/${encodeURIComponent(id)}`),
  submitDispute: (id, payload) =>
    req(`/disputes/${encodeURIComponent(id)}/submit`, { method: "POST", body: payload }),
  markDisputeSubmitted: (id, payload) =>
    req(`/disputes/${encodeURIComponent(id)}/mark-submitted`, { method: "POST", body: payload }),
};
