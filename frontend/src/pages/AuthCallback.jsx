import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { authProcess } from "../lib/api";

export default function AuthCallback() {
  const location = useLocation();
  const navigate = useNavigate();
  const processed = useRef(false);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;
    const hash = location.hash || window.location.hash;
    const m = hash.match(/session_id=([^&]+)/);
    if (!m) {
      navigate("/login", { replace: true });
      return;
    }
    const sid = decodeURIComponent(m[1]);
    (async () => {
      try {
        const user = await authProcess(sid);
        window.history.replaceState({}, "", "/dashboard");
        navigate("/dashboard", { replace: true, state: { user } });
      } catch (_e) {
        navigate("/login", { replace: true });
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#FAFAFC]">
      <div className="text-slate-600 text-sm">Autenticazione in corso…</div>
    </div>
  );
}
