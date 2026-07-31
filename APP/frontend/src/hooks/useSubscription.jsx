// Central hook for reading the user's tier, usage, and checking feature
// access on the frontend. Backend is still the source of truth (every
// gated route re-checks server-side) — this hook is purely for UI:
// showing/hiding buttons, disabling actions, displaying usage bars, and
// triggering the upgrade modal before a blocked request even fires.

import { useState, useEffect, useCallback, createContext, useContext } from "react";
import { api } from "@/lib/api";

const TIER_LIMITS = {
  free: {
    max_claimants: 1,
    sms_reminders: false,
    email_reminders_full_schedule: false,
    ai_screenshot_import: 0,
    ai_resume_review: 0,
    calendar_events: false,
    pdf_exports_per_month: 3,
    csv_export_full_history: false,
    document_storage_mb: 0,
    audit_log_days: 30,
    advanced_analytics: false,
    bulk_invite_management: false,
  },
  pro: {
    max_claimants: 1,
    sms_reminders: true,
    email_reminders_full_schedule: true,
    ai_screenshot_import: 10,
    ai_resume_review: 3,
    calendar_events: true,
    pdf_exports_per_month: null,
    csv_export_full_history: true,
    document_storage_mb: 100,
    audit_log_days: 365,
    advanced_analytics: true,
    bulk_invite_management: false,
  },
  caseworker: {
    max_claimants: null,
    sms_reminders: true,
    email_reminders_full_schedule: true,
    ai_screenshot_import: null,
    ai_resume_review: null,
    calendar_events: true,
    pdf_exports_per_month: null,
    csv_export_full_history: true,
    document_storage_mb: 1024,
    audit_log_days: 365,
    advanced_analytics: true,
    bulk_invite_management: true,
  },
};

const TIER_LABELS = { free: "Free", pro: "Pro", caseworker: "Case Worker" };

const SubscriptionContext = createContext(null);

export function SubscriptionProvider({ children }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/billing/status");
      setStatus(data);
    } catch (e) {
      // Not logged in yet, or billing route not reachable — default to free
      setStatus({ tier: "free", usage: {}, subscription: null });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const tier = status?.tier || "free";
  const limits = TIER_LIMITS[tier] || TIER_LIMITS.free;

  const hasFeature = useCallback(
    (feature) => Boolean(limits[feature]),
    [limits]
  );

  const getUsage = useCallback(
    (feature) => {
      const u = status?.usage?.[feature];
      const limit = limits[feature];
      return {
        used: u?.used ?? 0,
        limit: limit === undefined ? null : limit,
        unlimited: limit === null,
        remaining: limit === null ? Infinity : Math.max(0, (limit ?? 0) - (u?.used ?? 0)),
        exceeded: limit !== null && limit !== undefined && (u?.used ?? 0) >= limit,
      };
    },
    [status, limits]
  );

  const value = {
    tier,
    tierLabel: TIER_LABELS[tier],
    limits,
    loading,
    hasFeature,
    getUsage,
    refresh,
    isFree: tier === "free",
    isPro: tier === "pro",
    isCaseworker: tier === "caseworker",
  };

  return (
    <SubscriptionContext.Provider value={value}>
      {children}
    </SubscriptionContext.Provider>
  );
}

export function useSubscription() {
  const ctx = useContext(SubscriptionContext);
  if (!ctx) {
    throw new Error("useSubscription must be used within a SubscriptionProvider");
  }
  return ctx;
}