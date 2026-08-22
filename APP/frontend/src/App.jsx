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
import LegacyRedirect from "@/components/LegacyRedirect";
import { marketingUrl } from "@/lib/site";

// Eagerly load Layout — needed before any authenticated route renders
import Layout from "@/components/Layout";

// Lazily load every page so each route gets its own chunk.
// The router won't request a chunk until the user navigates to that path.
const SignIn        = lazy(() => import("@/pages/SignIn"));
const SignUp        = lazy(() => import("@/pages/SignUp"));
const Onboarding    = lazy(() => import("@/pages/Onboarding"));
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
      <div className="kbd-label text-muted-foreground">Loading…</div>
    </div>
  );
}

/**
 * Shown when Clerk never finishes initialising.
 *
 * Previously the route guards returned null in this state, so a bad
 * publishable key or a blocked clerk.browser.js rendered as a blank page with
 * nothing on screen and the only clue buried in the browser console.
 */
function AuthUnavailable() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-8">
      <div className="w-full max-w-lg">
        <div className="brand-bar w-20 mb-4" />
        <div className="kbd-label">Sign-in unavailable</div>
        <h1 className="font-display font-black text-2xl tracking-tighter mt-1">
          We couldn&apos;t reach the sign-in service
        </h1>
        <p className="text-sm text-muted-foreground mt-3 leading-relaxed">
          This is usually temporary. Try reloading; if it keeps happening, a
          browser extension may be blocking it, or the service may be briefly
          unavailable.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="bg-primary text-primary-foreground px-4 py-2 text-sm font-semibold hover:bg-primary-hover"
          >
            Reload
          </button>
          <a
            href={marketingUrl("/contact")}
            className="border border-border px-4 py-2 text-sm font-semibold hover:border-primary hover:text-primary"
          >
            Contact support
          </a>
        </div>
      </div>
    </div>
  );
}

/** Full-page loading state used by the route guards. */
function AuthLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="kbd-label">Loading…</div>
    </div>
  );
}

function Protected({ children }) {
  const { user, loading, needsOnboarding, clerkFailed } = useAuth();
  if (clerkFailed) return <AuthUnavailable />;
  if (loading) return <AuthLoading />;
  if (!user) return <Navigate to="/sign-in" replace />;
  // Clerk created the account but the claimant profile doesn't exist yet —
  // registration used to collect it in the same step.
  if (needsOnboarding) return <Navigate to="/onboarding" replace />;
  return children;
}

function PublicOnly({ children }) {
  const { user, loading, needsOnboarding, clerkFailed } = useAuth();
  if (clerkFailed) return <AuthUnavailable />;
  if (loading) return <AuthLoading />;
  if (user) {
    return <Navigate to={needsOnboarding ? "/onboarding" : "/dashboard"} replace />;
  }
  return <PublicChrome>{children}</PublicChrome>;
}

// Signed in, but deliberately reachable before onboarding is finished —
// Protected would bounce this route back to itself.
function RequiresAccount({ children }) {
  const { user, loading, clerkFailed } = useAuth();
  if (clerkFailed) return <AuthUnavailable />;
  if (loading) return <AuthLoading />;
  if (!user) return <Navigate to="/sign-in" replace />;
  return <PublicChrome>{children}</PublicChrome>;
}

// illinoisjobtracker.com owns the landing page, so the app no longer ships a
// second one competing with it for the same content and search results. Signed-
// in visitors still land straight on their dashboard.
function LandingOrApp() {
  const { user, loading, needsOnboarding, clerkFailed } = useAuth();
  if (clerkFailed) return <AuthUnavailable />;
  if (loading) return <AuthLoading />;
  if (user) {
    return <Navigate to={needsOnboarding ? "/onboarding" : "/dashboard"} replace />;
  }
  return <ExternalRedirect to={marketingUrl("/")} />;
}

// Derives the admin-platform role from the session. The backend now sends
// platform_role on /auth/me — it previously didn't, so this always fell
// through to the legacy `role === "admin"` branch.
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

              {/* Clerk owns these flows. The `/*` matters: <SignIn/> and
                  <SignUp/> route their own sub-steps (email verification,
                  factor choice, SSO callback, password reset) beneath the
                  same path. */}
              <Route
                path="/sign-in/*"
                element={
                  <PublicOnly>
                    <SignIn />
                  </PublicOnly>
                }
              />
              <Route
                path="/sign-up/*"
                element={
                  <PublicOnly>
                    <SignUp />
                  </PublicOnly>
                }
              />

              {/* Old paths kept as redirects: illinoisjobtracker.com links to
                  /login and /register, invitation emails are already out with
                  /invite/:code, and people have bookmarks. */}
              <Route path="/login" element={<LegacyRedirect to="/sign-in" />} />
              <Route path="/register" element={<LegacyRedirect to="/sign-up" />} />
              <Route path="/forgot-password" element={<LegacyRedirect to="/sign-in" />} />
              <Route path="/reset-password" element={<LegacyRedirect to="/sign-in" />} />
              <Route path="/verify-email" element={<LegacyRedirect to="/sign-in" />} />
              <Route path="/invite/:code" element={<LegacyRedirect to="/sign-up" />} />

              <Route
                path="/onboarding"
                element={
                  <RequiresAccount>
                    <Onboarding />
                  </RequiresAccount>
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
                  sign-up and SMS consent flows. */}
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
