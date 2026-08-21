import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { setToken } from "@/lib/tokenStorage";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  EnvelopeIcon,
  UserCircleIcon,
  ShieldCheckIcon,
} from "@phosphor-icons/react";
import { site } from "@/lib/site";

export default function InviteSignup() {
  const { code } = useParams();
  const [invite, setInvite] = useState(null);
  const [err, setErr] = useState("");
  const [form, setForm] = useState({ name: "", password: "", confirm: "" });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .get(`/invite/${code}`)
      .then((r) => setInvite(r.data))
      .catch((err) => setErr(formatApiError(err)));
  }, [code]);

  const submit = async (e) => {
    e.preventDefault();
    if (form.password !== form.confirm)
      return toast.error("Passwords do not match");
    setBusy(true);
    try {
      const { data } = await api.post("/invite/redeem", {
        code,
        password: form.password,
        name: form.name,
      });
      setToken(data.token);
      toast.success(`Welcome to ${site.name}`);
      window.location.href = "/dashboard";
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };

  if (err) {
    return (
      <div className="flex-1 flex items-center justify-center bg-background p-8">
        <div
          className="max-w-md w-full border border-[#DC2626] bg-destructive/10 p-6"
          data-testid="invite-error"
        >
          <h2 className="font-display font-bold text-xl text-[#DC2626]">
            Invite invalid
          </h2>
          <p className="text-sm text-foreground mt-2">{err}</p>
          <Link
            to="/login"
            className="inline-block mt-4 text-primary font-semibold underline"
          >
            Go to sign in
          </Link>
        </div>
      </div>
    );
  }
  if (!invite)
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="kbd-label">Loading invite…</div>
      </div>
    );

  return (
    <div className="flex-1 flex items-center justify-center bg-background p-8">
      <form
        onSubmit={submit}
        className="w-full max-w-md space-y-6"
        data-testid="invite-form"
      >
        <div>
          <div className="brand-bar w-20 mb-4" />
          <div className="kbd-label inline-flex items-center gap-2">
            <ShieldCheckIcon size={12} weight="bold" /> Case-Worker Invitation
          </div>
          <h2 className="font-display font-black text-3xl tracking-tighter mt-1">
            Accept invite
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            A case worker has set up your account.
          </p>
        </div>

        <div className="border border-border bg-secondary p-4 space-y-2 text-sm">
          <div className="flex items-center gap-2">
            <EnvelopeIcon size={14} weight="bold" className="text-primary" />{" "}
            <span className="font-semibold">{invite.email}</span>
          </div>
          <div className="flex items-center gap-2">
            <UserCircleIcon
              size={14}
              weight="bold"
              className="text-primary"
            />{" "}
            Claimant label:{" "}
            <span className="font-semibold">{invite.claimant_label}</span>
          </div>
          {invite.note && <div className="kbd-label">Note: {invite.note}</div>}
        </div>

        <div>
          <Label className="kbd-label">Your Full Name</Label>
          <Input
            required
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="rounded-none mt-2 border-border"
            data-testid="invite-name-input"
          />
        </div>
        <div>
          <Label className="kbd-label">Create Password</Label>
          <Input
            type="password"
            autoComplete="new-password"
            required
            minLength={6}
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            className="rounded-none mt-2 border-border"
            data-testid="invite-password-input"
          />
        </div>
        <div>
          <Label className="kbd-label">Confirm Password</Label>
          <Input
            type="password"
            autoComplete="new-password"
            required
            minLength={6}
            value={form.confirm}
            onChange={(e) => setForm({ ...form, confirm: e.target.value })}
            className="rounded-none mt-2 border-border"
            data-testid="invite-confirm-input"
          />
        </div>
        <Button
          type="submit"
          disabled={busy}
          className="w-full rounded-none bg-primary hover:bg-primary/90 h-11 font-semibold"
          data-testid="invite-submit-button"
        >
          {busy ? "Creating account..." : "Accept & create account"}
        </Button>
        <div className="text-xs text-muted-foreground">
          By accepting you agree this is an unofficial tool not affiliated with
          IDES.
        </div>
      </form>
    </div>
  );
}