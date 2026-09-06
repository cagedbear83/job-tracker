import { useEffect, useRef, useCallback } from "react";

const INACTIVITY_MS = 5 * 60 * 1000;        // 5 minutes → logout
const WARNING_MS   = INACTIVITY_MS - 60_000; // 4 minutes → warn

const ACTIVITY_EVENTS = [
  "mousemove",
  "mousedown",
  "keydown",
  "scroll",
  "touchstart",
  "click",
  "pointerdown",
];

/**
 * Automatically logs the user out after INACTIVITY_MS of no activity.
 *
 * @param {object} opts
 * @param {() => void}        opts.onLogout   - called when the idle timer fires
 * @param {() => void}        [opts.onWarning] - called 1 minute before logout
 * @param {() => void}        [opts.onResume]  - called when activity resumes
 *                                              after the warning fired (use to
 *                                              dismiss the warning toast)
 * @param {boolean}           [opts.enabled]  - set false to pause (e.g. when
 *                                              the user is not authenticated)
 */
export function useInactivityLogout({ onLogout, onWarning, onResume, enabled = true }) {
  const logoutRef   = useRef(null);
  const warningRef  = useRef(null);
  const warnedRef   = useRef(false);

  // Stable refs so the effect deps don't change on every render
  const onLogoutRef  = useRef(onLogout);
  const onWarningRef = useRef(onWarning);
  const onResumeRef  = useRef(onResume);
  useEffect(() => { onLogoutRef.current  = onLogout;  }, [onLogout]);
  useEffect(() => { onWarningRef.current = onWarning; }, [onWarning]);
  useEffect(() => { onResumeRef.current  = onResume;  }, [onResume]);

  const clear = useCallback(() => {
    clearTimeout(logoutRef.current);
    clearTimeout(warningRef.current);
  }, []);

  const reset = useCallback(() => {
    const previouslyWarned = warnedRef.current;
    clear();
    warnedRef.current = false;

    // If the warning was showing, tell the caller so it can dismiss the toast.
    if (previouslyWarned) {
      onResumeRef.current?.();
    }

    warningRef.current = setTimeout(() => {
      warnedRef.current = true;
      onWarningRef.current?.();
    }, WARNING_MS);

    logoutRef.current = setTimeout(() => {
      onLogoutRef.current?.();
    }, INACTIVITY_MS);
  }, [clear]);

  useEffect(() => {
    if (!enabled) {
      clear();
      return;
    }

    reset();

    const handler = () => reset();
    ACTIVITY_EVENTS.forEach((evt) =>
      window.addEventListener(evt, handler, { passive: true }),
    );

    return () => {
      clear();
      ACTIVITY_EVENTS.forEach((evt) =>
        window.removeEventListener(evt, handler),
      );
    };
  }, [enabled, reset, clear]);
}
