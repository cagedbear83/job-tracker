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
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-zinc-50 to-zinc-100 p-4">
      <div className="w-full max-w-md bg-white rounded-lg border border-zinc-200 shadow-sm p-8">
        <div className="text-center">
          <h1 className="font-display font-black text-2xl tracking-tight mb-2">
            Email Verification
          </h1>

          {noToken ? (
            <div className="space-y-4 py-8">
              <div className="text-4xl">✕</div>
              <p className="text-sm text-zinc-700 font-medium">
                No verification token provided.
              </p>
              <div className="space-y-2 mt-6">
                <Link to="/login">
                  <Button className="rounded-none bg-[#0033A0] hover:bg-[#002266] w-full">
                    Back to Login
                  </Button>
                </Link>
                <Link to="/register">
                  <Button
                    variant="outline"
                    className="rounded-none w-full border-zinc-300"
                  >
                    Create New Account
                  </Button>
                </Link>
              </div>
            </div>
          ) : (
            <div className="space-y-4 py-8">
              <div className="flex justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border border-[#0033A0] border-t-transparent" />
              </div>
              <p className="text-sm text-zinc-600">
                Verifying your email address...
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
