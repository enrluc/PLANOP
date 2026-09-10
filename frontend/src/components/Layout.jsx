import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/AuthContext";
import {
  LayoutDashboard, FileText, Users, CalendarDays, Route, Receipt, LogOut,
} from "lucide-react";
import { Button } from "./ui/button";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, testid: "nav-dashboard" },
  { to: "/contracts", label: "Contratti", icon: FileText, testid: "nav-contracts" },
  { to: "/clients", label: "Clienti", icon: Users, testid: "nav-clients" },
  { to: "/planning", label: "Planning", icon: Route, testid: "nav-planning" },
  { to: "/calendar", label: "Calendario", icon: CalendarDays, testid: "nav-calendar" },
  { to: "/invoices", label: "Fatture", icon: Receipt, testid: "nav-invoices" },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  if (!user) { navigate("/login"); return null; }

  return (
    <div className="min-h-screen flex flex-col lg:flex-row bg-[#FAFAFC]">
      <aside className="lg:w-64 lg:min-h-screen bg-white border-b lg:border-b-0 lg:border-r border-slate-200 flex-shrink-0">
        <div className="p-5 flex items-center gap-2 border-b border-slate-100">
          <div className="w-8 h-8 bg-slate-900 rounded-md flex items-center justify-center">
            <Route className="w-4 h-4 text-white" strokeWidth={2.5} />
          </div>
          <span className="font-display font-extrabold text-lg text-slate-900">PlanOp</span>
        </div>
        <nav className="p-3 flex lg:flex-col gap-1 overflow-x-auto lg:overflow-visible">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              data-testid={n.testid}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium whitespace-nowrap transition-colors
                ${isActive
                  ? "bg-slate-900 text-white"
                  : "text-slate-700 hover:bg-slate-100"}`
              }
            >
              <n.icon className="w-4 h-4" />
              <span>{n.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="hidden lg:block absolute bottom-0 lg:relative p-3 mt-auto border-t border-slate-100">
          <div className="flex items-center gap-2 p-2">
            {user.picture ? (
              <img src={user.picture} alt="" className="w-8 h-8 rounded-full" />
            ) : (
              <div className="w-8 h-8 rounded-full bg-slate-200" />
            )}
            <div className="flex-1 min-w-0">
              <div className="text-xs font-semibold text-slate-900 truncate">{user.name}</div>
              <div className="text-[11px] text-slate-500 truncate">{user.email}</div>
            </div>
            <Button
              data-testid="logout-button"
              variant="ghost" size="sm"
              onClick={logout}
              className="text-slate-500 hover:text-slate-900"
            >
              <LogOut className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </aside>

      <main className="flex-1 min-w-0 p-4 sm:p-6 lg:p-8">
        <Outlet />
      </main>
    </div>
  );
}
