import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import path from "path";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.ico", "icons/*.png"],
      manifest: {
        name: "Illinois Job Tracker",
        short_name: "Illinois Job Tracker",
        description: "Track IDES work-search contacts and benefit week compliance.",
        theme_color: "#0033A0",
        background_color: "#ffffff",
        display: "standalone",
        start_url: "/",
        scope: "/",
        icons: [
          {
            src: "icons/icon-192.png",
            sizes: "192x192",
            type: "image/png",
          },
          {
            src: "icons/icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any maskable",
          },
        ],
      },
      workbox: {
        // Precache JS/CSS/fonts for a fast offline-capable shell, but NOT
        // html. html used to be in this globPattern, which let Workbox's
        // precache-and-route register "/index.html" (and "/") as a
        // cache-first route — once a service worker was installed, it kept
        // serving whatever HTML+JS bundle was current AT INSTALL TIME,
        // forever, regardless of what was actually deployed, until that
        // exact service worker instance happened to get replaced through
        // its own update cycle.
        //
        // This is exactly what broke the Aug 20 session-security fix for a
        // returning visitor: a browser that had installed a service worker
        // any time before that fix shipped kept precache-serving the OLD
        // frontend bundle (the one that stored a 7-day JWT in localStorage)
        // even after the NEW backend + frontend session logic (10-min
        // access token, httpOnly rotating refresh cookie, 30-min idle /
        // 12h absolute expiry) was live — so a fully-closed-and-reopened
        // Chrome could still load the stale bundle, find the old,
        // still-unexpired localStorage token, and render "logged in" days
        // after the fix shipped, without the new code ever running.
        //
        // Fix: html is no longer precached at all; navigations instead use
        // the NetworkFirst runtime-caching entry below, so every visit
        // fetches the current index.html (and therefore whichever JS
        // bundle is actually deployed) from the network first, falling
        // back to the last-cached shell only if the network is
        // unreachable. JS/CSS/fonts stay precached — those are
        // content-hashed by Vite, so a stale cached asset is never served
        // under a URL a new deploy would also use.
        globPatterns: ["**/*.{js,css,woff2}"],
        navigateFallback: null,
        runtimeCaching: [
          {
            urlPattern: ({ request }) => request.mode === "navigate",
            handler: "NetworkFirst",
            options: {
              cacheName: "html-shell",
              networkTimeoutSeconds: 3,
            },
          },
          {
            // Cache the PWA manifest with a 24-hour TTL so the browser
            // doesn't re-fetch it on every navigation. Without this entry
            // the manifest isn't in any cache, and Cloudflare's WAF rate
            // limiter fires a 429 when the browser (and SW update checks)
            // request it repeatedly across a session.
            urlPattern: /\/manifest\.webmanifest$/,
            handler: "StaleWhileRevalidate",
            options: {
              cacheName: "pwa-manifest",
              expiration: {
                maxAgeSeconds: 60 * 60 * 24, // 24 hours
              },
            },
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  // Use 'static/' as the public dir so legacy public/index.html is ignored.
  // Static assets (favicon, icons) live in static/ and are served at /.
  publicDir: "static",
  server: {
    port: 3000,
  },
  build: {
    outDir: "build",
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          // Core React runtime — changes least often, cached longest
          "vendor-react": ["react", "react-dom"],
          // Router is small but separate from React so it caches independently
          "vendor-router": ["react-router-dom"],
          // All Radix primitives — large, almost never changes
          "vendor-radix": [
            "@radix-ui/react-accordion",
            "@radix-ui/react-alert-dialog",
            "@radix-ui/react-avatar",
            "@radix-ui/react-checkbox",
            "@radix-ui/react-dialog",
            "@radix-ui/react-dropdown-menu",
            "@radix-ui/react-label",
            "@radix-ui/react-popover",
            "@radix-ui/react-progress",
            "@radix-ui/react-radio-group",
            "@radix-ui/react-scroll-area",
            "@radix-ui/react-select",
            "@radix-ui/react-separator",
            "@radix-ui/react-slot",
            "@radix-ui/react-switch",
            "@radix-ui/react-tabs",
            "@radix-ui/react-toast",
            "@radix-ui/react-tooltip",
          ],
          // Charts library — heavy, loaded only on Dashboard
          "vendor-charts": ["recharts"],
          // Icons — tree-shaken but still a sizeable package
          "vendor-icons": ["@phosphor-icons/react"],
          // Form libraries
          "vendor-forms": [
            "react-hook-form",
            "zod",
            "@hookform/resolvers",
          ],
        },
      },
    },
  },
});
