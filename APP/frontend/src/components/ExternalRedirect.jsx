import { useEffect } from "react";

/**
 * Hands the visitor off to another origin — in practice, always
 * illinoisjobtracker.com, which owns every marketing and legal page.
 *
 * `replace` rather than `assign` so the app route never lands in history and
 * the browser Back button returns where the visitor actually came from instead
 * of bouncing them straight back out again.
 */
export default function ExternalRedirect({ to }) {
  useEffect(() => {
    window.location.replace(to);
  }, [to]);

  return (
    <div className="min-h-[40vh] flex items-center justify-center">
      <div className="kbd-label">Redirecting…</div>
    </div>
  );
}
