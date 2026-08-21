import React from "react";
import ReactDOM from "react-dom/client";
import { ThemeProvider } from "next-themes";

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

initSentry();

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
      <App />
    </ThemeProvider>
  </React.StrictMode>,
);
