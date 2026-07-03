import { useState } from "react";
import { Link } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { EnvelopeSimpleIcon } from "@phosphor-icons/react";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/auth/forgot-password", { email });
      setSent(true);
      toast.success("If that email exists, a reset link was sent.");
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-8">
      <form
        onSubmit={submit}
        className="w-full max-w-md space-y-6"
        data-testid="forgot-form"
      >
        <div>
          <div className="brand-bar w-20 mb-4" />
          <div className="kbd-label">Recovery</div>
          <h2 className="font-display font-black text-3xl tracking-tighter mt-1">
            Forgot password
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Enter your account email and we'll send a reset link.
          </p>
        </div>

        {sent ? (
          <div
            className="border border-[#16A34A] bg-green-50 dark:bg-green-950/30 p-6 text-sm"
            data-testid="forgot-success"
          >
            <EnvelopeSimpleIcon
              size={20}
              weight="bold"
              className="text-[#16A34A] mb-2"
            />
            <div className="font-semibold text-foreground">Check your inbox</div>
            <p className="mt-1 text-foreground">
              If <code>{email}</code> exists in our system, a reset link has
              been emailed. It expires in 1 hour.
            </p>
            <Link
              to="/login"
              className="inline-block mt-3 text-[#0033A0] dark:text-[#5a86ff] font-semibold underline"
            >
              Back to sign in
            </Link>
          </div>
        ) : (
          <>
            <div>
              <Label className="kbd-label">Email</Label>
              <Input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="rounded-none border-border mt-2"
                data-testid="forgot-email-input"
              />
            </div>
            <Button
              type="submit"
              disabled={busy}
              className="w-full rounded-none bg-[#0033A0] hover:bg-[#002266] text-white h-11 font-semibold"
              data-testid="forgot-submit-button"
            >
              {busy ? "Sending..." : "Send reset link"}
            </Button>
            <div className="text-xs">
              <Link to="/login" className="text-muted-foreground underline">
                ← Back to sign in
              </Link>
            </div>
          </>
        )}
      </form>
    </div>
  );
}