import { useEffect, useRef, useState } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [status, setStatus] = useState("loading");
  const [message, setMessage] = useState("");
  const redirectTimer = useRef(null);
  const token = searchParams.get("token");

  useEffect(() => {
    const verify = async () => {
      if (!token) {
        setStatus("error");
        setMessage("No verification token provided");
        return;
      }

      try {
        const response = await api.get(`/auth/verify-email?token=${token}`);
        setStatus("success");
        setMessage(response.data.message || "Email verified successfully!");
        toast.success("Your email has been verified");

        if (!user) {
          redirectTimer.current = setTimeout(() => navigate("/login"), 3000);
        }
      } catch (err) {
        setStatus("error");
        setMessage(formatApiError(err));
        toast.error(formatApiError(err));
      }
    };

    verify();

    return () => {
      if (redirectTimer.current) {
        clearTimeout(redirectTimer.current);
      }
    };
  }, [token, navigate, user]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted p-4">
      <div className="w-full max-w-md bg-card rounded-lg border border-border shadow-sm p-8">
        <div className="text-center">
          <h1 className="font-display font-black text-2xl tracking-tight mb-2">
            Email Verification
          </h1>

          {status === "loading" && (
            <div className="space-y-4 py-8">
              <div className="flex justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border border-[#0033A0] border-t-transparent" />
              </div>
              <p className="text-sm text-muted-foreground">
                Verifying your email address...
              </p>
            </div>
          )}

          {status === "success" && (
            <div className="space-y-4 py-8">
              <div className="text-4xl">✓</div>
              <p className="text-sm text-foreground font-medium">{message}</p>
              {!user && (
                <p className="text-xs text-muted-foreground">
                  Redirecting to login in 3 seconds...
                </p>
              )}
              <Button
                className="rounded-none bg-[#0033A0] hover:bg-[#002266] w-full mt-4"
                onClick={() => navigate(user ? "/dashboard" : "/login")}
              >
                {user ? "Go to Dashboard" : "Go to Login"}
              </Button>
            </div>
          )}

          {status === "error" && (
            <div className="space-y-4 py-8">
              <div className="text-4xl">✕</div>
              <p className="text-sm text-foreground font-medium">{message}</p>
              <div className="space-y-2 mt-6">
                <Button
                  className="rounded-none bg-[#0033A0] hover:bg-[#002266] w-full"
                  onClick={() => navigate(user ? "/dashboard" : "/login")}
                >
                  {user ? "Back to Dashboard" : "Back to Login"}
                </Button>
                {!user && (
                  <Link to="/register">
                    <Button variant="outline" className="rounded-none w-full border-border">
                      Create New Account
                    </Button>
                  </Link>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}