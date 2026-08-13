import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

const VERIFY_ERROR_MESSAGES = {
  invalid: "That verification link is invalid. Request a new one by registering again.",
  expired: "That verification link has expired. Register again to get a new one.",
};

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const verified = searchParams.get("verified") === "1";
  const verifyError = searchParams.get("verify_error");
  const verifyErrorMessage = verifyError
    ? VERIFY_ERROR_MESSAGES[verifyError] || "We couldn't verify your email. Please try again."
    : null;

  const onSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await login(email, password);
      toast.success("Welcome back");
      navigate("/dashboard");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen grid grid-cols-1 md:grid-cols-2 bg-white">
      <div className="hidden md:block relative">
        <img
          src="https://images.unsplash.com/photo-1657639789999-837194c7d6aa?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA2MDV8MHwxfHNlYXJjaHwxfHxpbGxpbm9pcyUyMGNoaWNhZ28lMjBza3lsaW5lfGVufDB8fHx8MTc3ODU0ODUxN3ww&ixlib=rb-4.1.0&q=85"
          alt="Chicago Skyline"
          className="w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-[#0033A0]/55" />
        <div className="absolute inset-0 p-12 flex flex-col justify-between text-white">
          <div className="brand-bar w-32" />
          <div>
            <div className="kbd-label text-white/70">State of Illinois</div>
            <h1 className="font-display font-black text-5xl lg:text-6xl tracking-tighter mt-2">
              Job Search<br/>Tracker
            </h1>
            <p className="text-white/80 mt-4 max-w-md leading-relaxed">
              Stay compliant with Illinois Unemployment Insurance work-search requirements.
              Log contacts, certify weeks, and export IDES-style reports.
            </p>
          </div>
          <div className="text-xs text-white/60">
            Unofficial tool — not affiliated with IDES. Mirrors ADJ034F form structure.
          </div>
        </div>
      </div>

      <div className="flex items-center justify-center p-8">
        <form onSubmit={onSubmit} className="w-full max-w-md space-y-6" data-testid="login-form">
          {verified && (
            <div
              role="status"
              className="rounded-none border border-green-300 bg-green-50 px-4 py-3 text-sm text-green-800"
              data-testid="verify-success-banner"
            >
              <span className="font-semibold">Email verified.</span> You can now sign in.
            </div>
          )}

          {verifyErrorMessage && (
            <div
              role="alert"
              className="rounded-none border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800"
              data-testid="verify-error-banner"
            >
              {verifyErrorMessage}
            </div>
          )}

          <div>
            <div className="brand-bar w-20 mb-4" />
            <div className="kbd-label">Authentication</div>
            <h2 className="font-display font-black text-3xl tracking-tighter mt-1">Sign in</h2>
            <p className="text-sm text-zinc-600 mt-1">
              Don't have an account?{" "}
              <Link to="/register" className="text-[#0033A0] font-semibold underline" data-testid="link-register">
                Create one
              </Link>
            </p>
          </div>

          <div className="space-y-3">
            <div>
              <Label htmlFor="email" className="kbd-label">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="rounded-none border-zinc-300 mt-2"
                data-testid="login-email-input"
              />
            </div>
            <div>
              <Label htmlFor="password" className="kbd-label">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="rounded-none border-zinc-300 mt-2"
                data-testid="login-password-input"
              />
            </div>
          </div>

          <Button
            type="submit"
            disabled={busy}
            className="w-full rounded-none bg-[#0033A0] hover:bg-[#002266] text-white h-11 font-semibold"
            data-testid="login-submit-button"
          >
            {busy ? "Signing in..." : "Sign in"}
          </Button>

          <div className="text-xs flex justify-between items-center">
            <Link to="/forgot-password" className="text-[#0033A0] underline font-semibold" data-testid="link-forgot">
              Forgot password?
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
