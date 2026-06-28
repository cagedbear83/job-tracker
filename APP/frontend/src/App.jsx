import "@/App.css";
import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import ErrorBoundary from "./components/ErrorBoundary";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { Toaster } from "@/components/ui/sonner";

// Eagerly load Layout and auth-wall pages — needed before any route renders
import Layout from "@/components/Layout";

// Lazily load every page so each route gets its own chunk.
// The router won't request a chunk until the user navigates to that path.
const Login         = lazy(() => import("@/pages/Login"));
const Register      = lazy(() => import("@/pages/Register"));
const ForgotPassword = lazy(() => import("@/pages/ForgotPassword"));
const ResetPassword = lazy(() => import("@/pages/ResetPassword"));
const VerifyEmail   = lazy(() => import("@/pages/VerifyEmail"));
const Landing       = lazy(() => import("@/pages/Landing"));
const InviteSignup  = lazy(() => import("@/pages/InviteSignup"));
const Dashboard     = lazy(() => import("@/pages/Dashboard"));
const Profile       = lazy(() => import("@/pages/Profile"));
const Claimants     = lazy(() => import("@/pages/Claimants"));
const CalendarPage  = lazy(() => import("@/pages/Calendar"));
const AdminPage     = lazy(() => import("@/pages/Admin"));
const BenefitWeeks  = lazy(() => import("@/pages/BenefitWeeks"));
const WeekDetail    = lazy(() => import("@/pages/WeekDetail"));
const ImportPage    = lazy(() => import("@/pages/ImportPage"));
const AuditLog      = lazy(() => import("@/pages/AuditLog"));
const DocumentsPage = lazy(() => import("@/pages/Documents"));
const SmsOptIn      = lazy(() => import("@/pages/SmsOptIn"));
const PrivacyPolicy = lazy(() => import("@/pages/PrivacyPolicy"));
const Terms         = lazy(() => import("@/pages/Terms"));

function PageLoader() {
  return (
    <div className="min-h-[40vh] flex items-center justify-center">
      <div className="kbd-label text-zinc-400">Loading…</div>
    </div>
  );
}

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

export function App() {
  return (
    <div className="App">
      <ErrorBoundary>
        <AuthProvider>
          <BrowserRouter>
            <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="/" element={<LandingOrApp />} />
              <Route
                path="/login"
                element={
                  <PublicOnly>
                    <Login />
                  </PublicOnly>
                }
              />
              <Route
                path="/register"
                element={
                  <PublicOnly>
                    <Register />
                  </PublicOnly>
                }
              />
              <Route
                path="/verify-email"
                element={
                  <PublicOnly>
                    <VerifyEmail />
                  </PublicOnly>
                }
              />
              <Route
                path="/forgot-password"
                element={
                  <PublicOnly>
                    <ForgotPassword />
                  </PublicOnly>
                }
              />
              <Route
                path="/reset-password"
                element={
                  <PublicOnly>
                    <ResetPassword />
                  </PublicOnly>
                }
              />
              <Route
                path="/invite/:code"
                element={
                  <PublicOnly>
                    <InviteSignup />
                  </PublicOnly>
                }
              />
              <Route
                path="/app"
                element={
                  <Protected>
                    <Layout />
                  </Protected>
                }
              >
                <Route index element={<Navigate to="/dashboard" replace />} />
              </Route>
              <Route
                element={
                  <Protected>
                    <Layout />
                  </Protected>
                }
              >
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/claimants" element={<Claimants />} />
                <Route path="/profile" element={<Profile />} />
                <Route path="/weeks" element={<BenefitWeeks />} />
                <Route path="/weeks/:id" element={<WeekDetail />} />
                <Route path="/calendar" element={<CalendarPage />} />
                <Route path="/documents" element={<DocumentsPage />} />
                <Route path="/import" element={<ImportPage />} />
                <Route path="/audit" element={<AuditLog />} />
                <Route path="/admin" element={<AdminPage />} />
                <Route path="/sms-opt-in" element={<SmsOptIn />} />
                <Route path="/privacy" element={<PrivacyPolicy />} />
                <Route path="/terms" element={<Terms />} />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
            </Suspense>
          </BrowserRouter>
          <Toaster richColors position="top-right" />
        </AuthProvider>
      </ErrorBoundary>
    </div>
  );
}

export default App;
