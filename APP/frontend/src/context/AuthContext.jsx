import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api, formatApiError } from "../lib/api";

const AuthCtx = createContext(null);

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
    const t = localStorage.getItem("ides_token");
    if (!t) { setLoading(false); return; }
    api.get("/auth/me")
      .then(async (r) => {
        setUser(r.data);
        if (r.data.role !== "admin") await refreshClaimants();
      })
      .catch(() => { localStorage.removeItem("ides_token"); })
      .finally(() => setLoading(false));
  }, [refreshClaimants]);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem("ides_token", data.token);
    setUser(data.user);
    if (data.user.role !== "admin") await refreshClaimants();
    return data.user;
  };

  const register = async (email, password, name) => {
    const { data } = await api.post("/auth/register", { email, password, name });
    localStorage.setItem("ides_token", data.token);
    setUser(data.user);
    await refreshClaimants();
    return data.user;
  };

  const logout = async () => {
    try { await api.post("/auth/logout"); } catch {}
    localStorage.removeItem("ides_token");
    setUser(null);
    setClaimants([]);
    setActiveClaimantId(null);
  };

  const setActiveClaimant = async (id) => {
    await api.post(`/claimants/${id}/set-active`);
    setActiveClaimantId(id);
  };

  return (
    <AuthCtx.Provider value={{
      user, loading, login, register, logout,
      claimants, activeClaimantId, refreshClaimants, setActiveClaimant,
    }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
export { formatApiError };
