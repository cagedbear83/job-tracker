import { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { API } from "@/lib/api";
import { Button } from "@/components/ui/button";

// Backward-compatibility shim.
//
// New verification emails link directly to the backend
// (`{PUBLIC_BACKEND_URL}/api/auth/verify-email`), which verifies the token and
// redirects to `/login?verified=1`. But emails sent BEFORE that change point
// here, at `{FRONTEND_URL}/verify-email?token=...`. Rather than make a
// cross-origin XHR from the SPA (the old behavior, which is what triggered the
// CORS/429 errors), we forward the browser to the backend endpoint so those
// older links go through the same CORS-free redirect flow.
export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const [noToken, setNoToken] = useState(false);
  const token = searchParams.get("token");

  useEffect(() => {
    if (!token) {
      setNoToken(true);
      return;
    }
    // Top-level navigation (not an XHR) → no CORS, no preflight. The backend
    // verifies and redirects on to /login?verified=1 (or ?verify_error=...).
    window.location.replace(
      `${API}/auth/verify-email?token=${encodeURIComponent(token)}`,
    );
  }, [token]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-md border border-border bg-card">
        {/* Branded header — same "IL" badge + product name treatment used in
            the reminder emails (see core.py's _reminder_html), so this page
            reads as the same product rather than a generic status screen. */}
        <div className="bg-primary px-6 py-5 flex items-center gap-3">
          <div className="bg-white text-primary font-display font-black text-lg w-9 h-9 flex items-center justify-center flex-shrink-0">
            IL
          </div>
          <div>
            <div className="text-white font-display font-black text-sm tracking-tight leading-none">
              Illinois UI Job Search Tracker
            </div>
            <div className="text-white/70 text-[10px] uppercase tracking-widest mt-1">
              Work Search Compliance
            </div>
          </div>
        </div>

        <div className="p-8 text-center">
          <h1 className="font-display font-black text-2xl tracking-tight mb-2">
            Email Verification
          </h1>

          {noToken ? (
            <div className="space-y-4 py-8">
              <div
                className="mx-auto flex items-center justify-center w-12 h-12 rounded-full border border-destructive/40 bg-destructive/10 text-destructive text-2xl"
                aria-hidden="true"
              >
                ✕
              </div>
              <p className="text-sm text-foreground font-medium">
                No verification token provided.
              </p>
              <p className="text-xs text-muted-foreground">
                Check that you followed the full link from your verification
                email, or request a new one below.
              </p>
              <div className="space-y-2 mt-6">
                <Link to="/login">
                  <Button className="rounded-none bg-primary hover:bg-primary/90 w-full">
                    Back to Login
                  </Button>
                </Link>
                <Link to="/register">
                  <Button
                    variant="outline"
                    className="rounded-none w-full border-border"
                  >
                    Create New Account
                  </Button>
                </Link>
              </div>
            </div>
          ) : (
            <div className="space-y-4 py-8">
              <div className="flex justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-2 border-primary border-t-transparent" />
              </div>
              <p className="text-sm text-muted-foreground">
                Verifying your email address...
              </p>
            </div>
          )}
        </div>

        <div className="border-t border-border px-6 py-3 text-center text-[11px] text-muted-foreground">
          Unofficial tool — not affiliated with IDES.
        </div>
      </div>
    </div>
  );
}
