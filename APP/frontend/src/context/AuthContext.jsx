import { createContext, useContext, useEffect, useRef, useState } from "react";
import { api, formatApiError, refreshSession } from "../lib/api";
import { setToken, clearToken } from "../lib/tokenStorage";

const AuthCtx = createContext(null);

// How long a signed-in tab can sit with no mouse/keyboard/touch activity
// before we log the user out client-side. This is a UX-level backstop on
// top of (not a replacement for) the backend's own sliding refresh-token
// expiry (REFRESH_TOKEN_IDLE_MINUTES, currently 30 min) — this fires first
// so an unattended, still-open tab doesn't sit around for the full window.
const IDLE_LOGOUT_MINUTES = 15;
const ACTIVITY_EVENTS = ["mousedown", "keydown", "scroll", "touchstart", "click"];

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const logoutRef = useRef(() => {});

  useEffect(() => {
    let cancelled = false;
    (async () => {
      // There's no persisted access token to check on a fresh page load
      // (it only ever lives in memory) — instead, try to silently mint one
      // from the httpOnly refresh cookie, if a valid one exists.
      const token = await refreshSession();
      if (!token) {
        if (!cancelled) setLoading(false);
        return;
      }
      try {
        const { data } = await api.get("/auth/me");
        if (!cancelled) setUser(data);
      } catch {
        clearToken();
        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    setToken(data.token);
    setUser(data.user);
    return data.user;
  };

  const register = async (body) => {
    // Registration no longer returns a session token — the account must be
    // verified via email before it can log in (see /auth/login).
    const { data } = await api.post("/auth/register", body);
    return data.user;
  };

  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      // Logout should always succeed locally even if the server call fails
      // (e.g. token already expired) — we still clear local state below.
    }
    clearToken();
    setUser(null);
  };

  // Keep a stable ref to the latest `logout` so the idle-timer effect below
  // doesn't need to re-bind its listeners every render.
  logoutRef.current = logout;

  useEffect(() => {
    if (!user) return undefined;
    let timeoutId;
    const scheduleLogout = () => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        logoutRef.current();
      }, IDLE_LOGOUT_MINUTES * 60 * 1000);
    };
    ACTIVITY_EVENTS.forEach((evt) =>
      window.addEventListener(evt, scheduleLogout, { passive: true }),
    );
    scheduleLogout();
    return () => {
      clearTimeout(timeoutId);
      ACTIVITY_EVENTS.forEach((evt) =>
        window.removeEventListener(evt, scheduleLogout),
      );
    };
  }, [user]);

  return (
    <AuthCtx.Provider
      value={{
        user,
        loading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
export { formatApiError };
