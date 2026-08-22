import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useAuth as useClerkAuth, useUser } from "@clerk/clerk-react";
import { api, formatApiError } from "../lib/api";

const AuthCtx = createContext(null);

/**
 * Bridges Clerk's session to this app's notion of a user.
 *
 * Clerk answers "is someone signed in, and who are they" — but everything the
 * app actually gates on (role, platform_role, active claimant, whether
 * onboarding is done) lives in our own database. So this provider waits for
 * Clerk to settle, then fetches /auth/me, which provisions the local user row
 * on first contact (see backend clerk_auth.get_or_create_user).
 *
 * Gone from here, because Clerk owns them now: login(), register(), the
 * in-memory access token, the silent refresh on mount, and the idle-logout
 * timer (Clerk enforces session lifetime and inactivity server-side —
 * configure it under Sessions in the Clerk dashboard).
 */
export function AuthProvider({ children }) {
  const { isLoaded: clerkLoaded, isSignedIn, signOut } = useClerkAuth();
  const { user: clerkUser } = useUser();

  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Clerk can fail to initialise entirely — a wrong publishable key, a
  // production instance whose DNS has not propagated, an ad blocker eating
  // clerk.browser.js. When that happens `isLoaded` simply stays false
  // forever, and every route guard below sits in its loading branch, which
  // rendered as a blank page with nothing in the UI to explain it.
  // Time it out so the failure is visible instead of silent.
  const [clerkTimedOut, setClerkTimedOut] = useState(false);
  useEffect(() => {
    if (clerkLoaded) return undefined;
    const t = setTimeout(() => setClerkTimedOut(true), 8000);
    return () => clearTimeout(t);
  }, [clerkLoaded]);

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
        // Signed in to Clerk but our API refused. Rather than sitting in a
        // half-authenticated state, drop the local user and let the route
        // guards send them back to sign-in.
        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
    // clerkUser?.id so switching accounts in the same tab refetches.
  }, [clerkLoaded, isSignedIn, clerkUser?.id]);

  const logout = useCallback(async () => {
    setUser(null);
    await signOut();
  }, [signOut]);

  return (
    <AuthCtx.Provider
      value={{
        user,
        // Stay "loading" until Clerk has settled AND we know who the user is,
        // so route guards never briefly see a signed-in session as anonymous.
        loading: (!clerkLoaded || loading) && !clerkTimedOut,
        clerkFailed: clerkTimedOut && !clerkLoaded,
        logout,
        refreshUser,
        // Drives the post-signup redirect into /onboarding.
        needsOnboarding: Boolean(user?.needs_onboarding),
      }}
    >
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
export { formatApiError };
