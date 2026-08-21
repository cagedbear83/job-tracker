import React from "react";
import ReactDOM from "react-dom/client";
import { ThemeProvider } from "next-themes";
import { ClerkProvider } from "@clerk/clerk-react";

// Self-hosted so the app and illinoisjobtracker.com load the same faces the
// same way — no render-blocking third-party stylesheet, no FOUT on one domain
// and not the other. Weights match next/font on the marketing site exactly.
import "@fontsource/chivo/400.css";
import "@fontsource/chivo/700.css";
import "@fontsource/chivo/900.css";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-sans/700.css";

import "@/index.css";
import App from "@/App";
import { initSentry } from "@/lib/sentry";
import { THEME_STORAGE_KEY } from "@/lib/site";
import ClerkTokenBridge from "@/components/ClerkTokenBridge";
import { clerkAppearance } from "@/lib/clerkAppearance";

initSentry();

// Publishable key is safe in the bundle by design — it identifies the Clerk
// instance to the browser and grants nothing. The secret key (sk_...) must
// never appear here; it lives only in the backend environment.
const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

if (!PUBLISHABLE_KEY) {
  throw new Error(
    "VITE_CLERK_PUBLISHABLE_KEY is not set. Add it to .env locally and to the " +
      "Vercel environment variables, then redeploy — the app cannot " +
      "authenticate anyone without it.",
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    {/* `system` matches the marketing site's default, so a visitor with a dark
        OS doesn't get a dark .com and a light .app. The inline script in
        index.html has already applied the resolved theme (and consumed any
        ?theme= handed off from .com) before first paint. */}
    <ThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
      storageKey={THEME_STORAGE_KEY}
    >
      {/* ClerkProvider sits inside ThemeProvider so the appearance tokens it
          reads (hsl(var(--primary)) and friends) resolve against whichever
          theme is active — Clerk's screens follow dark mode for free. */}
      <ClerkProvider
        publishableKey={PUBLISHABLE_KEY}
        appearance={clerkAppearance}
        signInUrl="/sign-in"
        signUpUrl="/sign-up"
        afterSignOutUrl="/sign-in"
      >
        <ClerkTokenBridge />
        <App />
      </ClerkProvider>
    </ThemeProvider>
  </React.StrictMode>,
);
