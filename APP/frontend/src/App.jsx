import "@/App.css";
import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import ErrorBoundary from "./components/ErrorBoundary";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { Toaster } from "@/components/ui/sonner";
import { UpgradeModalProvider } from "@/components/UpgradeModal";
import { SubscriptionProvider } from "@/hooks/useSubscription";
import RequireRole from "@/components/RequireRole";
import ExternalRedirect from "@/components/ExternalRedirect";
import PublicChrome from "@/components/PublicChrome";
import { marketingUrl } from "@/lib/site";

// Eagerly load Layout and auth-wall pages — needed before any route renders
import Layout from "@/components/Layout";

// Lazily load every page so each route gets its own chunk.
// The router won't request a chunk until the user navigates to that path.
const Login         = lazy(() => import("@/pages/Login"));
const Register      = lazy(() => import("@/pages/Register"));
const ForgotPassword = lazy(() => import("@/pages/ForgotPassword"));
const ResetPassword = lazy(() => import("@/pages/ResetPassword"));
const VerifyEmail   = lazy(() => import("@/pages/VerifyEmail"));
const InviteSignup  = lazy(() => import("@/pages/InviteSignup"));
const Dashboard     = lazy(() => import("@/pages/Dashboard"));
const Profile       = lazy(() => import("@/pages/Profile"));
const CalendarPage  = lazy(() => import("@/pages/Calendar"));
const AdminPage     = lazy(() => import("@/pages/Admin"));
const AdminPlatform = lazy(() => import("@/pages/AdminPlatform"));
const BenefitWeeks  = lazy(() => import("@/pages/BenefitWeeks"));
const WeekDetail    = lazy(() => import("@/pages/WeekDetail"));
const ImportPage    = lazy(() => import("@/pages/ImportPage"));
const AuditLog      = lazy(() => import("@/pages/AuditLog"));
const DocumentsPage = lazy(() => import("@/pages/Documents"));
const SmsOptIn      = lazy(() => import("@/pages/SmsOptIn"));

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
  return <PublicChrome>{children}</PublicChrome>;
}

// illinoisjobtracker.com owns the landing page, so the app no longer ships a
// second one competing with it for the same content and search results. Signed-
// in visitors still land straight on their dashboard.
function LandingOrApp() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/dashboard" replace />;
  return <ExternalRedirect to={marketingUrl("/")} />;
}

// Derives the new admin-platform role from the existing session until the
// platform_role migration (backend/admin_rbac_migration.py) has run — mirrors
// rbac.py's own legacy-role fallback so frontend and backend agree.
function platformRoleFor(user) {
  if (user?.platform_role) return user.platform_role;
  return user?.role === "admin" ? "platform_admin" : "user";
}

// Gates the new /admin/platform surface (see src/pages/AdminPlatform.jsx).
// Kept separate from the existing /admin route/page — the two are
// independent admin surfaces, matching the backend's namespacing.
function AdminPlatformRoute() {
  const { user } = useAuth();
  const role = platformRoleFor(user);
  return (
    <RequireRole atLeast="support_staff" role={role} fallback={<Navigate to="/dashboard" replace />}>
      <AdminPlatform currentRole={role} />
    </RequireRole>
  );
}

export function App() {
  return (
    <div className="App">
      <ErrorBoundary>
        <SubscriptionProvider>
          <UpgradeModalProvider>
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
                <Route path="/profile" element={<Profile />} />
                <Route path="/weeks" element={<BenefitWeeks />} />
                <Route path="/weeks/:id" element={<WeekDetail />} />
                <Route path="/calendar" element={<CalendarPage />} />
                <Route path="/documents" element={<DocumentsPage />} />
                <Route path="/import" element={<ImportPage />} />
                <Route path="/audit" element={<AuditLog />} />
                <Route path="/admin" element={<AdminPage />} />
                <Route path="/admin/platform" element={<AdminPlatformRoute />} />
                <Route path="/sms-opt-in" element={<SmsOptIn />} />
              </Route>
              {/* Legal lives on the marketing site, and these must stay
                  reachable while logged out — they are linked from the
                  registration and SMS consent flows. They used to sit behind
                  the auth wall, which bounced exactly those visitors to
                  /login. */}
              <Route
                path="/privacy"
                element={<ExternalRedirect to={marketingUrl("/privacy")} />}
              />
              <Route
                path="/terms"
                element={<ExternalRedirect to={marketingUrl("/terms")} />}
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
            </Suspense>
          </BrowserRouter>
          <Toaster richColors position="top-right" />
        </AuthProvider>
        </UpgradeModalProvider>
        </SubscriptionProvider>
      </ErrorBoundary>
    </div>
  );
}

export default App;
