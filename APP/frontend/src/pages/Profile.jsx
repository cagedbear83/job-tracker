import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { FeatureGate } from "@/components/FeatureGate";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  FloppyDiskIcon,
  EnvelopeSimpleIcon,
  DeviceMobile as DeviceMobileIcon,
  PaperPlaneTiltIcon,
  WarningIcon,
  TrashIcon,
} from "@phosphor-icons/react";

const FIELDS = [
  ["first_name", "First Name", "sm:col-span-6"],
  ["middle_initial", "MI", "sm:col-span-2"],
  ["last_name", "Last Name", "sm:col-span-4"],
  ["claimant_id", "Claimant ID", "sm:col-span-4"],
  ["phone", "Phone", "sm:col-span-4"],
  ["occupation", "Occupation", "sm:col-span-4"],
  ["address", "Address", "sm:col-span-8"],
  ["city", "City", "sm:col-span-4"],
  ["state", "State", "sm:col-span-2"],
  ["zip_code", "ZIP", "sm:col-span-2"],
];

const blankForm = () => ({
  first_name: "",
  last_name: "",
  middle_initial: "",
  claimant_id: "",
  address: "",
  city: "",
  state: "IL",
  zip_code: "",
  phone: "",
  occupation: "",
  reminders_enabled: true,
  reminder_email: "",
  sms_enabled: false,
});

export default function Profile() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState(blankForm());
  const [profileId, setProfileId] = useState(null);
  const [smsVerified, setSmsVerified] = useState(false);
  const [smsPhone, setSmsPhone] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = () =>
    api.get("/profile").then((r) => {
      if (r.data) {
        setForm({ ...blankForm(), ...r.data });
        setProfileId(r.data.id || null);
        setSmsVerified(Boolean(r.data.sms_verified));
        setSmsPhone(r.data.sms_phone || "");
      }
    });

  useEffect(() => {
    load().finally(() => setLoading(false));
  }, []);

  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const save = async (e) => {
    if (e?.preventDefault) e.preventDefault();
    setBusy(true);
    try {
      await api.put("/profile", form);
      toast.success("Profile saved");
      await load();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  const sendTest = async (kind) => {
    try {
      const { data } = await api.post(`/reminders/test?kind=${kind}`);
      toast.success(`Sent ${data.sent} reminder email(s)`);
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };

  // ── SMS OTP verification ────────────────────────────────────────────────
  const [otpStep, setOtpStep] = useState(0); // 0 closed, 1 send, 2 verify
  const [otpPhone, setOtpPhone] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [otpBusy, setOtpBusy] = useState(false);

  const openOtp = () => {
    setOtpPhone(smsPhone || form.phone || "");
    setOtpCode("");
    setOtpStep(1);
  };
  const sendOtp = async () => {
    setOtpBusy(true);
    try {
      await api.post("/sms/send-otp", { claimant_id: profileId, phone: otpPhone });
      toast.success(`Code sent to ${otpPhone}`);
      setOtpStep(2);
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setOtpBusy(false);
    }
  };
  const verifyOtp = async () => {
    setOtpBusy(true);
    try {
      await api.post("/sms/verify-otp", { claimant_id: profileId, code: otpCode });
      toast.success("Phone verified — SMS reminders enabled");
      setOtpStep(0);
      await load();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setOtpBusy(false);
    }
  };

  // ── Delete account ──────────────────────────────────────────────────────
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [confirmEmail, setConfirmEmail] = useState("");
  const [confirmName, setConfirmName] = useState("");
  const [confirmChecked, setConfirmChecked] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const norm = (s) => (s || "").trim().replace(/\s+/g, " ").toLowerCase();
  const expectedName = `${form.first_name || ""} ${form.last_name || ""}`.trim();
  const emailMatches =
    norm(confirmEmail) === norm(user?.email) && !!user?.email;
  const nameMatches = !!expectedName && norm(confirmName) === norm(expectedName);
  const canDelete = emailMatches && nameMatches && confirmChecked && !deleting;

  const resetDelete = () => {
    setConfirmEmail("");
    setConfirmName("");
    setConfirmChecked(false);
  };

  const doDelete = async () => {
    setDeleting(true);
    try {
      await api.post("/account/delete", {
        email: confirmEmail,
        confirm_name: confirmName,
        confirm: confirmChecked,
      });
      setDeleteOpen(false);
      toast.success("Your account has been deleted.");
      await logout();
      navigate("/login");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setDeleting(false);
    }
  };

  if (loading) return <div className="kbd-label">Loading...</div>;

  return (
    <div className="space-y-6" data-testid="profile-page">
      <div>
        <div className="kbd-label">Identity</div>
        <h1 className="font-display font-black text-4xl tracking-tighter mt-1">
          Claimant Profile
        </h1>
        <p className="text-sm text-muted-foreground mt-2 max-w-2xl">
          Your profile populates IDES work-search reports.
        </p>
      </div>

      {/* ── Identity ── */}
      <form onSubmit={save} className="border border-border bg-card p-6 sm:p-8">
        <div className="grid grid-cols-12 gap-4">
          {FIELDS.map(([key, label, span]) => (
            <div key={key} className={`col-span-12 ${span}`}>
              <Label className="kbd-label">{label}</Label>
              <Input
                value={form[key] || ""}
                onChange={(e) => setField(key, e.target.value)}
                className="rounded-none border-border mt-2"
                data-testid={`profile-${key}-input`}
              />
            </div>
          ))}
        </div>
        <div className="mt-6 flex gap-2">
          <Button
            type="submit"
            disabled={busy}
            className="rounded-none bg-primary hover:bg-primary/90"
            data-testid="profile-save-button"
          >
            <FloppyDiskIcon size={16} weight="bold" className="mr-2" />{" "}
            {busy ? "Saving..." : "Save Profile"}
          </Button>
        </div>
      </form>

      {/* ── Notifications ── */}
      <div className="border border-border bg-card p-6 sm:p-8 space-y-6">
        <div>
          <div className="kbd-label">Notifications</div>
          <h2 className="font-display font-bold text-xl tracking-tight mt-1">
            Email &amp; SMS Reminders
          </h2>
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
            Weekly work-search reminders are sent Sun, Wed, Fri, and Sat at 9 AM CT.
          </p>
        </div>

        {/* Email */}
        <div className="border-t border-border pt-4">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.reminders_enabled}
              onChange={(e) => setField("reminders_enabled", e.target.checked)}
              data-testid="profile-reminders-toggle"
            />
            <EnvelopeSimpleIcon size={16} weight="bold" />
            Receive weekly email reminders
          </label>
          <div className="mt-3 max-w-md">
            <Label className="kbd-label">
              Reminder email (leave blank to use your account email)
            </Label>
            <Input
              value={form.reminder_email}
              onChange={(e) => setField("reminder_email", e.target.value)}
              placeholder={user?.email || "yourname@email.com"}
              className="rounded-none border-border mt-2"
              data-testid="profile-reminder-email"
            />
          </div>
        </div>

        {/* SMS */}
        <div className="border-t border-border pt-4">
          <label className="flex items-start gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={form.sms_enabled}
              onChange={(e) => setField("sms_enabled", e.target.checked)}
              className="mt-0.5"
              data-testid="profile-sms-toggle"
            />
            <span>
              <span className="inline-flex items-center gap-1 font-medium">
                <DeviceMobileIcon size={16} weight="bold" />
                Also send SMS reminders
              </span>
              <span className="block text-xs text-muted-foreground mt-1 leading-relaxed">
                By checking this box, you agree to receive automated SMS
                certification-deadline reminders from{" "}
                <strong>Illinois UI Job Search Tracker</strong> at the phone
                number below. Message frequency varies. Message and data
                rates may apply. Reply <strong>HELP</strong> for help and{" "}
                <strong>STOP</strong> to opt out at any time. View our{" "}
                <Link to="/terms" className="text-primary underline" target="_blank">
                  Terms &amp; Conditions
                </Link>{" "}
                and{" "}
                <Link to="/privacy" className="text-primary underline" target="_blank">
                  Privacy Policy
                </Link>
                .
              </span>
            </span>
          </label>
          {form.sms_enabled && (
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <span
                className={`text-xs font-semibold uppercase tracking-wider px-2 py-0.5 border ${
                  smsVerified
                    ? "border-primary text-primary"
                    : "border-[#EAB308] text-[#EAB308]"
                }`}
              >
                {smsVerified ? `SMS verified ${smsPhone}` : "Phone not verified"}
              </span>
              <FeatureGate feature="sms_reminders">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="rounded-none border-border"
                  onClick={openOtp}
                  disabled={!profileId}
                  data-testid="profile-verify-phone"
                >
                  {smsVerified ? "Re-verify phone" : "Verify phone"}
                </Button>
              </FeatureGate>
            </div>
          )}
          <p className="text-xs text-muted-foreground mt-2">
            No SMS is sent until the number is verified with a one-time code.
          </p>
        </div>

        {/* Save + test sends */}
        <div className="border-t border-border pt-4 flex flex-wrap items-center gap-2">
          <Button
            type="button"
            onClick={save}
            disabled={busy}
            className="rounded-none bg-primary hover:bg-primary/90"
            data-testid="save-notifications-button"
          >
            <FloppyDiskIcon size={16} weight="bold" className="mr-2" />
            {busy ? "Saving..." : "Save notification settings"}
          </Button>
          <span className="kbd-label ml-2">Send test:</span>
          {["sunday", "wednesday", "friday", "saturday"].map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => sendTest(k)}
              data-testid={`test-${k}`}
              className="text-xs font-semibold uppercase tracking-wider border border-border px-2 py-1 hover:border-primary hover:text-primary inline-flex items-center gap-1"
            >
              <PaperPlaneTiltIcon size={11} weight="bold" /> {k.slice(0, 3)}
            </button>
          ))}
        </div>
      </div>

      {/* ── Danger zone ── */}
      <div className="border border-destructive/40 bg-destructive/5 p-6 sm:p-8">
        <div className="kbd-label text-destructive">Danger Zone</div>
        <h2 className="font-display font-bold text-xl tracking-tight mt-1">
          Delete Profile
        </h2>
        <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
          Permanently delete your account and every record attached to it —
          your profile, benefit weeks, work-search contacts, calendar events,
          documents, and history.
        </p>
        <Button
          type="button"
          className="mt-4 rounded-none bg-destructive hover:bg-destructive/90 text-white"
          onClick={() => {
            resetDelete();
            setDeleteOpen(true);
          }}
          data-testid="delete-profile-button"
        >
          <TrashIcon size={16} weight="bold" className="mr-2" /> Delete my profile
        </Button>
      </div>

      {/* Delete confirmation dialog */}
      <Dialog
        open={deleteOpen}
        onOpenChange={(o) => {
          setDeleteOpen(o);
          if (!o) resetDelete();
        }}
      >
        <DialogContent className="rounded-none" data-testid="delete-confirm-dialog">
          <DialogHeader>
            <DialogTitle className="font-display tracking-tight flex items-center gap-2 text-destructive">
              <WarningIcon size={20} weight="fill" /> Delete your profile?
            </DialogTitle>
          </DialogHeader>

          <div className="border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            Your access is revoked <b>immediately</b> and every record attached
            to your account is <b>permanently deleted</b> after 30 days. This
            cannot be undone.
          </div>

          <div className="space-y-3 mt-2">
            <div>
              <Label className="kbd-label">Type your email to confirm</Label>
              <Input
                value={confirmEmail}
                onChange={(e) => setConfirmEmail(e.target.value)}
                placeholder={user?.email || ""}
                className="rounded-none border-border mt-2"
                data-testid="delete-confirm-email"
              />
            </div>
            <div>
              <Label className="kbd-label">
                Type your full name{expectedName ? ` (${expectedName})` : ""}
              </Label>
              <Input
                value={confirmName}
                onChange={(e) => setConfirmName(e.target.value)}
                className="rounded-none border-border mt-2"
                data-testid="delete-confirm-name"
              />
            </div>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                checked={confirmChecked}
                onChange={(e) => setConfirmChecked(e.target.checked)}
                className="mt-1"
                data-testid="delete-confirm-check"
              />
              I understand this deletes my account and all of my data, and it
              cannot be undone.
            </label>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              className="rounded-none"
              onClick={() => setDeleteOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              className="rounded-none bg-destructive hover:bg-destructive/90 text-white disabled:opacity-50"
              disabled={!canDelete}
              onClick={doDelete}
              data-testid="delete-confirm-submit"
            >
              {deleting ? "Deleting..." : "Delete permanently"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* SMS OTP dialog */}
      <Dialog open={otpStep > 0} onOpenChange={(o) => { if (!o) setOtpStep(0); }}>
        <DialogContent className="rounded-none" data-testid="otp-dialog">
          <DialogHeader>
            <DialogTitle className="font-display tracking-tight">
              Verify SMS phone
            </DialogTitle>
          </DialogHeader>
          {otpStep === 1 && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Enter the phone in E.164 format. We'll text a 6-digit code.
              </p>
              <Input
                value={otpPhone}
                onChange={(e) => setOtpPhone(e.target.value)}
                placeholder="+13125550100"
                className="rounded-none border-border"
                data-testid="otp-phone-input"
              />
              <Button
                type="button"
                onClick={sendOtp}
                disabled={otpBusy || !otpPhone.startsWith("+")}
                className="rounded-none bg-primary hover:bg-primary/90 w-full"
                data-testid="otp-send-button"
              >
                {otpBusy ? "Sending..." : "Send code"}
              </Button>
            </div>
          )}
          {otpStep === 2 && (
            <div className="space-y-3">
              <p className="text-sm text-foreground">
                Enter the 6-digit code we texted to <b>{otpPhone}</b>.
              </p>
              <Input
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ""))}
                maxLength={6}
                placeholder="123456"
                className="rounded-none border-border font-mono tracking-widest text-center text-xl"
                data-testid="otp-code-input"
              />
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  className="rounded-none flex-1"
                  onClick={() => setOtpStep(1)}
                >
                  Back
                </Button>
                <Button
                  type="button"
                  onClick={verifyOtp}
                  disabled={otpBusy || otpCode.length !== 6}
                  className="rounded-none bg-primary hover:bg-primary/90 flex-1"
                  data-testid="otp-verify-button"
                >
                  {otpBusy ? "Verifying..." : "Verify"}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
