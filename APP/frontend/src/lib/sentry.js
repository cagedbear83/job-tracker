// Frontend error tracking. No-op unless VITE_SENTRY_DSN is set, so local
// and preview builds without a DSN are completely unaffected.
import * as Sentry from "@sentry/react";

let initialized = false;

export function initSentry() {
  const dsn = import.meta.env.VITE_SENTRY_DSN;
  if (!dsn || initialized) return;

  Sentry.init({
    dsn,
    environment: import.meta.env.VITE_SENTRY_ENVIRONMENT || "production",
    // Keep tracing modest by default; tune per environment.
    tracesSampleRate: Number(
      import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE || "0.1",
    ),
    // Don't capture PII (emails, claimant data) by default.
    sendDefaultPii: false,
  });
  initialized = true;
}

export function captureException(error, context) {
  if (!initialized) return;
  Sentry.captureException(error, context);
}
