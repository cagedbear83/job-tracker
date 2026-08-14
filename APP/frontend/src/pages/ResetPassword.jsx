import { useState } from "react";
import { Link, useSearchParams, useNavigate } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (password !== confirm) {
      return toast.error("Passwords do not match");
    }
    setBusy(true);
    try {
      await api.post("/auth/reset-password", { token, password });
      toast.success("Password reset. Please sign in.");
      navigate("/login");
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-8">
      <form onSubmit={submit} className="w-full max-w-md space-y-6" data-testid="reset-form">
        <div>
          <div className="brand-bar w-20 mb-4" />
          <div className="kbd-label">Set New Password</div>
          <h2 className="font-display font-black text-3xl tracking-tighter mt-1">Reset password</h2>
        </div>

        {!token ? (
          <div className="text-sm text-[#DC2626]">Missing or invalid reset token. <Link to="/forgot-password" className="underline">Request a new link</Link>.</div>
        ) : (
          <>
            <div>
              <Label className="kbd-label">New Password</Label>
              <Input type="password" autoComplete="new-password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} className="rounded-none border-border mt-2" data-testid="reset-password-input" />
            </div>
            <div>
              <Label className="kbd-label">Confirm Password</Label>
              <Input type="password" autoComplete="new-password" required minLength={6} value={confirm} onChange={(e) => setConfirm(e.target.value)} className="rounded-none border-border mt-2" data-testid="reset-confirm-input" />
            </div>
            <Button type="submit" disabled={busy} className="w-full rounded-none bg-primary hover:bg-primary/90 text-white h-11 font-semibold" data-testid="reset-submit-button">
              {busy ? "Resetting..." : "Reset password"}
            </Button>
          </>
        )}
      </form>
    </div>
  );
}
