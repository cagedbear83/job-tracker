import { createContext, useContext, useEffect, useState } from "react";
import { api, formatApiError } from "../lib/api";
import { getToken, setToken, clearToken } from "../lib/tokenStorage";

const AuthCtx = createContext(null);

// Token validation utilities
function isTokenExpired(token) {
  if (!token) return true;
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return true;

    // Decode payload
    const payload = JSON.parse(
      atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")),
    );
    const exp = payload.exp;

    if (!exp) return false;
    return Date.now() >= exp * 1000;
  } catch {
    return true;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = getToken();

    // Check if token exists and is not expired before making API call
    if (!t || isTokenExpired(t)) {
      if (t) {
        clearToken();
      }
      setLoading(false);
      return;
    }

    api
      .get("/auth/me")
      .then((r) => {
        setUser(r.data);
      })
      .catch(() => {
        clearToken();
        setUser(null);
      })
      .finally(() => setLoading(false));
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