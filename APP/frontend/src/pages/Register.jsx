import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await register(form.email, form.password, form.name);
      toast.success("Account created");
      navigate("/dashboard");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-white p-8">
      <form onSubmit={onSubmit} className="w-full max-w-md space-y-6" data-testid="register-form">
        <div>
          <div className="brand-bar w-20 mb-4" />
          <div className="kbd-label">New Account</div>
          <h2 className="font-display font-black text-3xl tracking-tighter mt-1">Register</h2>
          <p className="text-sm text-zinc-600 mt-1">
            Already have an account?{" "}
            <Link to="/login" className="text-[#0033A0] font-semibold underline" data-testid="link-login">
              Sign in
            </Link>
          </p>
        </div>

        <div className="space-y-3">
          <div>
            <Label className="kbd-label">Full Name</Label>
            <Input
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="rounded-none border-zinc-300 mt-2"
              data-testid="register-name-input"
            />
          </div>
          <div>
            <Label className="kbd-label">Email</Label>
            <Input
              type="email"
              required
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="rounded-none border-zinc-300 mt-2"
              data-testid="register-email-input"
            />
          </div>
          <div>
            <Label className="kbd-label">Password</Label>
            <Input
              type="password"
              required
              minLength={6}
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              className="rounded-none border-zinc-300 mt-2"
              data-testid="register-password-input"
            />
          </div>
        </div>

        <Button
          type="submit"
          disabled={busy}
          className="w-full rounded-none bg-[#0033A0] hover:bg-[#002266] text-white h-11 font-semibold"
          data-testid="register-submit-button"
        >
          {busy ? "Creating account..." : "Create account"}
        </Button>
      </form>
    </div>
  );
}
