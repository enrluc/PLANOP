import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { authMe, authLogout } from "./api";

const AuthCtx = createContext(null);

// Baked-in at build time. When "true" the desktop Electron build skips OAuth
// entirely and uses the local single-user account created by the backend.
const LOCAL_MODE = process.env.REACT_APP_LOCAL_MODE === "true";

const LOCAL_USER = {
  user_id: "local_user_001",
  email: "local@planop.desktop",
  name: "PlanOp Desktop",
  picture: "",
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(LOCAL_MODE ? LOCAL_USER : null);
  const [loading, setLoading] = useState(!LOCAL_MODE);

  const check = useCallback(async () => {
    if (LOCAL_MODE) {
      setUser(LOCAL_USER);
      setLoading(false);
      return;
    }
    try {
      const u = await authMe();
      setUser(u);
    } catch (_e) {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (LOCAL_MODE) {
      setLoading(false);
      return;
    }
    // CRITICAL: If returning from OAuth callback, skip the /me check.
    // AuthCallback will exchange the session_id and establish the session first.
    if (window.location.hash?.includes("session_id=")) {
      setLoading(false);
      return;
    }
    check();
  }, [check]);

  const logout = async () => {
    if (LOCAL_MODE) return; // no-op in desktop mode
    try { await authLogout(); } catch (_e) { /* ignore */ }
    setUser(null);
    window.location.href = "/login";
  };

  return (
    <AuthCtx.Provider value={{ user, setUser, loading, refresh: check, logout, localMode: LOCAL_MODE }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
export const IS_LOCAL_MODE = LOCAL_MODE;
