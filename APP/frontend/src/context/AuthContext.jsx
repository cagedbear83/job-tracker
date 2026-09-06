import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { useAuth as useClerkAuth, useUser } from "@clerk/clerk-react";
import { api, formatApiError } from "../lib/api";

const AuthCtx = createContext(null);

// sessionStorage: survives page refreshes but is wiped when the tab/browser
// closes. We use this to detect when a user returns after closing the browser
// while Clerk's cookie-backed session is still technically valid.
const TAB_SESSION_KEY = "ijt_tab_active";

// localStorage: shared across all open tabs. We write a timestamp here on
// logout so other tabs can hear the event and sign out too.
const LOGOUT_BROADCAST_KEY = "ijt_logout_at";

/**
 * Bridges Clerk's session to this app's notion of a user.
 *
 * Clerk answers "is someone signed in, and who are they" — but everything the
 * app actually gates on (role, platform_role, active claimant, whether
 * onboarding is done) lives in our own database. So this provider waits for
 * Clerk to settle, then fetches /auth/me, which provisions the local user row
 * on first contact (see backend clerk_auth.get_or_create_user).
 *
 * Session security enforced here (beyond Clerk's own token lifetime):
 *
 *  1. Browser/tab close  – sessionStorage flag is wiped when the tab closes.
 *     On the next load, if Clerk still has a valid cookie but there is no flag,
 *     we force a sign-out. This prevents a shared/borrowed device from being
 *     left signed in.
 *
 *  2. Cross-tab logout   – writing LOGOUT_BROADCAST_KEY to localStorage fires
 *     a `storage` event in every other open tab, which calls signOut there too.
 *
 *  3. Inactivity timeout – handled by useInactivityLogout in Layout.jsx;
 *     calls the logout() function exported from this context after 5 min idle.
 *
 *  4. Server revocation  – /auth/me returns 4xx → user set to null → route
 *     guards redirect to /sign-in automatically.
 */
export function AuthProvider({ children }) {
  const { isLoaded: clerkLoaded, isSignedIn, signOut } = useClerkAuth();
  const { user: clerkUser } = useUser();

  const [user, setUser]               = useState(null);
  const [loading, setLoading]         = useState(true);
  const [clerkTimedOut, setClerkTimedOut] = useState(false);

  // ─── Clerk timeout (unchanged) ──────────────────────────────────────────
  useEffect(() => {
    if (clerkLoaded) return undefined;
    const t = setTimeout(() => setClerkTimedOut(true), 8000);
    return () => clearTimeout(t);
  }, [clerkLoaded]);

  // ─── Browser-close / tab-close detection ────────────────────────────────
  // We only run the check once — on the very first tick that Clerk has loaded.
  // If isSignedIn is already true but there is no sessionStorage flag, the
  // user returned after closing the browser. Force sign-out immediately.
  const browserCloseChecked = useRef(false);

  useEffect(() => {
    if (!clerkLoaded || browserCloseChecked.current) return;
    browserCloseChecked.current = true;

    if (isSignedIn && !sessionStorage.getItem(TAB_SESSION_KEY)) {
      // Session survived browser close. Revoke it.
      signOut();
      return;
    }
  }, [clerkLoaded, isSignedIn, signOut]);

  // Keep the flag in sync whenever the user is signed in.
  useEffect(() => {
    if (!clerkLoaded) return;
    if (isSignedIn) {
      sessionStorage.setItem(TAB_SESSION_KEY, "1");
    }
  }, [clerkLoaded, isSignedIn]);

  // ─── Cross-tab logout sync ───────────────────────────────────────────────
  useEffect(() => {
    const handler = (e) => {
      if (e.key === LOGOUT_BROADCAST_KEY && e.newValue) {
        // Another tab signed out — mirror it here without setting the broadcast
        // key again (that would create a loop).
        sessionStorage.removeItem(TAB_SESSION_KEY);
        signOut();
      }
    };
    window.addEventListener("storage", handler);
    return () => window.removeEventListener("storage", handler);
  }, [signOut]);

  // ─── User hydration ──────────────────────────────────────────────────────
  const refreshUser = useCallback(async () => {
    const { data } = await api.get("/auth/me");
    setUser(data);
    return data;
  }, []);

  useEffect(() => {
    if (!clerkLoaded) return undefined;

    if (!isSignedIn) {
      setUser(null);
      setLoading(false);
      return undefined;
    }

    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const { data } = await api.get("/auth/me");
        if (!cancelled) setUser(data);
      } catch {
        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [clerkLoaded, isSignedIn, clerkUser?.id]);

  // ─── Logout ──────────────────────────────────────────────────────────────
  const logout = useCallback(async () => {
    // Remove tab flag so, if the same tab stays open and the user somehow
    // ends up signed back in via Clerk, the check still fires correctly.
    sessionStorage.removeItem(TAB_SESSION_KEY);

    // Notify every other open tab to sign out too.
    localStorage.setItem(LOGOUT_BROADCAST_KEY, String(Date.now()));

    setUser(null);
    await signOut();
  }, [signOut]);

  return (
    <AuthCtx.Provider
      value={{
        user,
        loading: (!clerkLoaded || loading) && !clerkTimedOut,
        clerkFailed: clerkTimedOut && !clerkLoaded,
        logout,
        refreshUser,
        needsOnboarding: Boolean(user?.needs_onboarding),
      }}
    >
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
export { formatApiError };
