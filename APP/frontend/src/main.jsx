import React from "react";
import { QueryClient, QueryClientProvider, QueryCache, MutationCache } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { toast } from "sonner";
import { formatApiError } from "@/lib/api";
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

const queryClient = new QueryClient({
  // ── Global error handlers ────────────────────────────────────────────────
  queryCache: new QueryCache({
    onError: (error, query) => {
      // Only toast on first-load failures (no cached data yet).
      // Background refetch failures are silent — the stale data stays visible.
      if (query.state.data === undefined) {
        toast.error(formatApiError(error));
      }
    },
  }),
  mutationCache: new MutationCache({
    onError: (error, _variables, _context, mutation) => {
      // Mutations that handle their own error UI set meta.suppressGlobalError.
      // Everything else gets a toast here so no onError boilerplate is needed.
      if (mutation.meta?.suppressGlobalError) return;
      toast.error(formatApiError(error));
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 60_000,          // 60 s — data is fresh for a minute
      gcTime:    5 * 60_000,      // 5 min — keep unused cache around
      retry: 1,
      refetchOnWindowFocus: true, // re-validate when the tab regains focus
    },
  },
});

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
        <QueryClientProvider client={queryClient}>
          <App />
          <ReactQueryDevtools initialIsOpen={false} />
        </QueryClientProvider>
      </ClerkProvider>
    </ThemeProvider>
  </React.StrictMode>,
);
