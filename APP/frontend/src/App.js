import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { Toaster } from "@/components/ui/sonner";

import Login from "@/pages/Login";
import Register from "@/pages/Register";
import ForgotPassword from "@/pages/ForgotPassword";
import ResetPassword from "@/pages/ResetPassword";
import Landing from "@/pages/Landing";
import InviteSignup from "@/pages/InviteSignup";
import Layout from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import Profile from "@/pages/Profile";
import Claimants from "@/pages/Claimants";
import CalendarPage from "@/pages/Calendar";
import AdminPage from "@/pages/Admin";
import BenefitWeeks from "@/pages/BenefitWeeks";
import WeekDetail from "@/pages/WeekDetail";
import ImportPage from "@/pages/ImportPage";
import AuditLog from "@/pages/AuditLog";
import SmsOptIn from "@/pages/SmsOptIn";
import PrivacyPolicy from "@/pages/PrivacyPolicy";
import Terms from "@/pages/Terms";

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="kbd-label">Loading...</div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function PublicOnly({ children }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/dashboard" replace />;
  return children;
}

function LandingOrApp() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/dashboard" replace />;
  return <Landing />;
}

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<LandingOrApp />} />
            <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
            <Route path="/register" element={<PublicOnly><Register /></PublicOnly>} />
            <Route path="/forgot-password" element={<PublicOnly><ForgotPassword /></PublicOnly>} />
            <Route path="/reset-password" element={<PublicOnly><ResetPassword /></PublicOnly>} />
            <Route path="/invite/:code" element={<PublicOnly><InviteSignup /></PublicOnly>} />
            <Route
              path="/app"
              element={<Protected><Layout /></Protected>}
            >
              <Route index element={<Navigate to="/dashboard" replace />} />
            </Route>
            <Route
              element={<Protected><Layout /></Protected>}
            >
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/claimants" element={<Claimants />} />
              <Route path="/profile" element={<Profile />} />
              <Route path="/weeks" element={<BenefitWeeks />} />
              <Route path="/weeks/:id" element={<WeekDetail />} />
              <Route path="/calendar" element={<CalendarPage />} />
              <Route path="/import" element={<ImportPage />} />
              <Route path="/audit" element={<AuditLog />} />
              <Route path="/admin" element={<AdminPage />} />
              <Route path="/sms-opt-in" element={<SmsOptIn />} />
              <Route path="/privacy" element={<PrivacyPolicy />} />
              <Route path="/terms" element={<Terms />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
        <Toaster richColors position="top-right" />
      </AuthProvider>
    </div>
  );
}

export default App;
