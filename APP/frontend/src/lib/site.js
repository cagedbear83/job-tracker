// Shared constants for the two halves of the product. Mirrors the overlapping
// fields in ijt-marketing/lib/site.ts — keep them in sync.
//
// illinoisjobtracker.com is the marketing and legal surface;
// illinoisjobtracker.app is the product. Every link from the app back to .com
// goes through marketingUrl() so there is exactly one place to change it.

export const site = {
  name: "Illinois Job Tracker",
  tagline:
    "Track your weekly work-search contacts and generate your ADJ034F — without the spreadsheet.",
  company: "KMG123 Enterprises LLC",
  supportEmail: "support@illinoisjobtracker.com",
  marketingUrl:
    import.meta.env.VITE_MARKETING_URL || "https://illinoisjobtracker.com",
};

/** Absolute URL to a page on the marketing site. */
export function marketingUrl(path = "/") {
  return `${site.marketingUrl}${path}`;
}

// next-themes storage key. Both domains use the same name so the two sites stay
// conceptually one product; the value itself can't be shared, since .com and
// .app are separate origins — that is what the ?theme= handoff consumed by the
// inline script in index.html is for.
export const THEME_STORAGE_KEY = "ijt-theme";
