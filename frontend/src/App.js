import "@/App.css";
import { BrowserRouter, Routes, Route, useLocation, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/lib/AuthContext";
import Login from "@/pages/Login";
import AuthCallback from "@/pages/AuthCallback";
import Layout from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import Contracts from "@/pages/Contracts";
import Clients from "@/pages/Clients";
import Planning from "@/pages/Planning";
import CalendarPage from "@/pages/CalendarPage";
import MapPage from "@/pages/MapPage";
import Invoices from "@/pages/Invoices";
import AIAssistant from "@/pages/AIAssistant";
import SettingsPage from "@/pages/Settings";
import { Toaster } from "@/components/ui/sonner";

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen flex items-center justify-center text-slate-500">Caricamento…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function AppRouter() {
  const location = useLocation();
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Protected><Layout /></Protected>}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="contracts" element={<Contracts />} />
        <Route path="clients" element={<Clients />} />
        <Route path="planning" element={<Planning />} />
        <Route path="calendar" element={<CalendarPage />} />
        <Route path="map" element={<MapPage />} />
        <Route path="ai" element={<AIAssistant />} />
        <Route path="invoices" element={<Invoices />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <AppRouter />
          <Toaster position="top-right" richColors />
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
