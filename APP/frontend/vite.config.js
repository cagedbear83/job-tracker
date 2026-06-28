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
        name: "Illinois UI Job Search Tracker",
        short_name: "IL UI Tracker",
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
        // Cache the SPA shell and static assets; let API calls go network-first
        globPatterns: ["**/*.{js,css,html,woff2}"],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
            handler: "CacheFirst",
            options: {
              cacheName: "google-fonts-cache",
              expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 365 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            urlPattern: /^https:\/\/fonts\.gstatic\.com\/.*/i,
            handler: "CacheFirst",
            options: {
              cacheName: "gstatic-fonts-cache",
              expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 365 },
              cacheableResponse: { statuses: [0, 200] },
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
