import { useEffect, useRef } from "react";

// Must match (or be ≤) the inactivity timeout so users can't bypass the
// inactivity guard simply by closing the laptop lid.
const THRESHOLD_MS = 5 * 60 * 1000; // 5 minutes

/**
 * Signs the user out when either:
 *
 *  a) The tab was hidden for longer than THRESHOLD_MS (laptop lid closed,
 *     screen locked, phone screen off). Browsers heavily throttle JS timers
 *     on hidden pages, so the inactivity hook alone does not catch this.
 *     We timestamp when the page goes hidden and check the gap on return.
 *
 *  b) The network was offline for longer than THRESHOLD_MS. Fires when the
 *     connection is restored — the user never sees the app in this state.
 *
 * Both reasons are reported back via separate callbacks so the caller can
 * show a descriptive toast.
 *
 * @param {object} opts
 * @param {(reason: 'hidden'|'offline') => void} opts.onLogout
 * @param {boolean} [opts.enabled]
 */
export function useOfflineLogout({ onLogout, enabled = true }) {
  const onLogoutRef  = useRef(onLogout);
  const hiddenAtRef  = useRef(null);   // timestamp when tab went hidden
  const offlineAtRef = useRef(null);  // timestamp when network dropped
  const firedRef     = useRef(false); // prevent double-fire if both trigger

  useEffect(() => { onLogoutRef.current = onLogout; }, [onLogout]);

  useEffect(() => {
    if (!enabled) return;

    firedRef.current = false;

    const fire = (reason) => {
      if (firedRef.current) return;
      firedRef.current = true;
      onLogoutRef.current?.(reason);
    };

    // ── Tab visibility ─────────────────────────────────────────────────────
    const handleVisibility = () => {
      if (document.hidden) {
        hiddenAtRef.current = Date.now();
      } else {
        const at = hiddenAtRef.current;
        hiddenAtRef.current = null;
        if (at !== null && Date.now() - at >= THRESHOLD_MS) {
          fire("hidden");
        }
      }
    };

    // ── Network ────────────────────────────────────────────────────────────
    const handleOffline = () => {
      offlineAtRef.current = Date.now();
    };

    const handleOnline = () => {
      const at = offlineAtRef.current;
      offlineAtRef.current = null;
      if (at !== null && Date.now() - at >= THRESHOLD_MS) {
        fire("offline");
      }
    };

    document.addEventListener("visibilitychange", handleVisibility);
    window.addEventListener("offline", handleOffline);
    window.addEventListener("online", handleOnline);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
      window.removeEventListener("offline", handleOffline);
      window.removeEventListener("online", handleOnline);
      // Reset timestamps so they don't carry over if `enabled` toggles.
      hiddenAtRef.current  = null;
      offlineAtRef.current = null;
      firedRef.current     = false;
    };
  }, [enabled]);
}
