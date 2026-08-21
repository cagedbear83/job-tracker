// Shows automatically when any API call returns HTTP 402 (Payment Required)
// — the status code our backend gate_feature()/gate_metered() helpers use
// for both "feature not on your plan" and "quota exceeded this month".
// Wire the trigger via an axios response interceptor in src/lib/api.js
// (snippet at the bottom of this file).

import { useState, useEffect, createContext, useContext, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { CrownIcon, CheckIcon, XIcon } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { marketingUrl } from "@/lib/site";

const UpgradeModalContext = createContext(null);

// Prices keyed by billing interval. The modal has a monthly/annual toggle
// and passes the chosen interval to the checkout endpoint.
const PLANS = [
  {
    tier: "pro",
    name: "Pro",
    price: { monthly: "$9.99", annual: "$95.99" },
    period: { monthly: "/month", annual: "/year" },
    features: [
      "1 claimant profile (your own)",
      "SMS + full email reminder schedule",
      "10 AI screenshot imports / month",
      "3 AI resume reviews / month",
      "Calendar events",
      "Unlimited PDF exports",
      "Full history CSV export",
      "100MB document storage",
      "12-month audit log",
    ],
    highlight: true,
  },
  {
    tier: "caseworker",
    name: "Case Worker",
    price: { monthly: "$19.99", annual: "$199.99" },
    period: { monthly: "/mo · first seat", annual: "/yr · first seat" },
    subnote: {
      monthly: "+ $12.99/mo per additional seat",
      annual: "+ $129.99/yr per additional seat",
    },
    features: [
      "Unlimited claimant profiles (per seat)",
      "Signed claimant liability release required",
      "SMS + full email reminder schedule",
      "Unlimited AI screenshot imports",
      "Unlimited AI resume reviews",
      "Calendar events",
      "Unlimited PDF exports",
      "Full history CSV export",
      "1GB document storage per seat",
      "12-month audit log",
      "Bulk invite + seat management",
    ],
    highlight: false,
  },
];

export function UpgradeModalProvider({ children }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState(null);
  const [checkingOut, setCheckingOut] = useState(null);
  const [interval, setBillingInterval] = useState("monthly"); // "monthly" | "annual"

  const show = useCallback((detail) => {
    setReason(detail || null);
    setOpen(true);
  }, []);

  useEffect(() => {
    // Listen for the custom event dispatched by the axios interceptor
    // (see snippet at bottom of file). Using a window event keeps this
    // decoupled from api.js so either file can be edited independently.
    const handler = (evt) => show(evt.detail);
    window.addEventListener("upgrade-required", handler);
    return () => window.removeEventListener("upgrade-required", handler);
  }, [show]);

  const handleUpgrade = async (tier) => {
    setCheckingOut(tier);
    try {
      // seats defaults to 1 here; the dedicated seat-management UI (in the
      // Admin panel, built later) handles adding seats to an existing
      // Case Worker subscription after initial checkout.
      const { data } = await api.post("/billing/checkout", { tier, interval, seats: 1 });
      window.location.href = data.checkout_url;
    } catch {
      setCheckingOut(null);
    }
  };

  return (
    <UpgradeModalContext.Provider value={{ show }}>
      {children}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="rounded-none max-w-3xl">
          <DialogHeader>
            <div className="flex items-center gap-2">
              <CrownIcon size={20} weight="fill" className="text-primary" />
              <DialogTitle className="font-display tracking-tight">
                Upgrade to unlock this feature
              </DialogTitle>
            </div>
            {reason?.message && (
              <p className="text-sm text-muted-foreground mt-2">{reason.message}</p>
            )}
          </DialogHeader>

          {/* Monthly / Annual toggle */}
          <div className="flex items-center justify-center gap-1 mt-4 mb-2">
            <button
              onClick={() => setBillingInterval("monthly")}
              className={`px-4 py-1.5 text-sm font-semibold border transition-colors ${
                interval === "monthly"
                  ? "bg-primary text-white border-primary"
                  : "bg-background text-muted-foreground border-border hover:border-muted-foreground"
              }`}
            >
              Monthly
            </button>
            <button
              onClick={() => setBillingInterval("annual")}
              className={`px-4 py-1.5 text-sm font-semibold border transition-colors ${
                interval === "annual"
                  ? "bg-primary text-white border-primary"
                  : "bg-background text-muted-foreground border-border hover:border-muted-foreground"
              }`}
            >
              Annual <span className="text-[10px] font-bold text-[#16A34A]">SAVE ~20%</span>
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-2">
            {PLANS.map((plan) => (
              <div
                key={plan.tier}
                className={`border p-5 flex flex-col ${
                  plan.highlight ? "border-primary border-2" : "border-border"
                }`}
              >
                {plan.highlight && (
                  <span className="text-[10px] font-bold tracking-widest text-primary uppercase mb-2">
                    Most Popular
                  </span>
                )}
                <h3 className="font-display font-black text-xl tracking-tight">
                  {plan.name}
                </h3>
                <div className="flex items-baseline gap-1 mt-1">
                  <span className="text-2xl font-black">{plan.price[interval]}</span>
                  <span className="text-sm text-muted-foreground">{plan.period[interval]}</span>
                </div>
                {plan.subnote && (
                  <div className="text-xs text-muted-foreground mb-3 mt-0.5">
                    {plan.subnote[interval]}
                  </div>
                )}
                {!plan.subnote && <div className="mb-4" />}
                <ul className="space-y-2 flex-1 mb-4">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-sm text-foreground">
                      <CheckIcon size={14} weight="bold" className="text-[#16A34A] mt-0.5 flex-shrink-0" />
                      {f}
                    </li>
                  ))}
                </ul>
                <Button
                  className={`rounded-none w-full ${
                    plan.highlight
                      ? "bg-primary hover:bg-primary/90"
                      : "bg-foreground text-background hover:bg-foreground/90"
                  }`}
                  disabled={checkingOut === plan.tier}
                  onClick={() => handleUpgrade(plan.tier)}
                >
                  {checkingOut === plan.tier ? "Redirecting..." : `Upgrade to ${plan.name}`}
                </Button>
              </div>
            ))}
          </div>

          {/* The full, canonical plan comparison lives on the marketing site.
              These cards are a summary; that page is the source of truth. */}
          <p className="mt-4 text-center text-xs text-muted-foreground">
            <a
              href={marketingUrl("/pricing")}
              target="_blank"
              rel="noreferrer"
              className="text-primary underline"
            >
              Compare all plans
            </a>{" "}
            on illinoisjobtracker.com
          </p>

          <button
            onClick={() => setOpen(false)}
            className="absolute top-4 right-4 text-muted-foreground hover:text-foreground"
          >
            <XIcon size={18} weight="bold" />
          </button>
        </DialogContent>
      </Dialog>
    </UpgradeModalContext.Provider>
  );
}

export function useUpgradeModal() {
  const ctx = useContext(UpgradeModalContext);
  if (!ctx) {
    throw new Error("useUpgradeModal must be used within an UpgradeModalProvider");
  }
  return ctx;
}

/* ═══════════════════════════════════════════════════════════════════════
   INTEGRATION SNIPPET — add to src/lib/api.js

   Add this response interceptor right after your existing request
   interceptor (the one that attaches the Bearer token). It catches any
   402 response globally so you don't need to handle upgrade prompts in
   every single component that calls a gated endpoint.

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

   Then in App.js, wrap your routes:

     import { UpgradeModalProvider } from "@/components/UpgradeModal";
     import { SubscriptionProvider } from "@/hooks/useSubscription";

     <SubscriptionProvider>
       <UpgradeModalProvider>
         <Routes>...</Routes>
       </UpgradeModalProvider>
     </SubscriptionProvider>
     ============================================================================ */