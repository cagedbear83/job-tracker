import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
} from "react";
import { api, formatApiError } from "../lib/api";

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
  const [claimants, setClaimants] = useState([]);
  const [activeClaimantId, setActiveClaimantId] = useState(null);

  const refreshClaimants = useCallback(async () => {
    try {
      const { data } = await api.get("/claimants");
      setClaimants(data.items || []);
      setActiveClaimantId(data.active_id || null);
    } catch {
      setClaimants([]);
      setActiveClaimantId(null);
    }
  }, []);

  useEffect(() => {
    const t = sessionStorage.getItem("ides_token");

    // Check if token exists and is not expired before making API call
    if (!t || isTokenExpired(t)) {
      if (t) {
        sessionStorage.removeItem("ides_token");
      }
      setLoading(false);
      return;
    }

    api
      .get("/auth/me")
      .then(async (r) => {
        setUser(r.data);
        if (r.data.role !== "admin") await refreshClaimants();
      })
      .catch(() => {
        sessionStorage.removeItem("ides_token");
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, [refreshClaimants]);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    sessionStorage.setItem("ides_token", data.token);
    setUser(data.user);
    if (data.user.role !== "admin") await refreshClaimants();
    return data.user;
  };

  const register = async (body) => {
    const { data } = await api.post("/auth/register", body);
    sessionStorage.setItem("ides_token", data.token);
    setUser(data.user);
    await refreshClaimants();
    return data.user;
  };

  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } catch {}
    sessionStorage.removeItem("ides_token");
    setUser(null);
    setClaimants([]);
    setActiveClaimantId(null);
  };

  const setActiveClaimant = async (id) => {
    await api.post(`/claimants/${id}/set-active`);
    setActiveClaimantId(id);
  };

  return (
    <AuthCtx.Provider
      value={{
        user,
        loading,
        login,
        register,
        logout,
        claimants,
        activeClaimantId,
        refreshClaimants,
        setActiveClaimant,
      }}
    >
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
export { formatApiError };
