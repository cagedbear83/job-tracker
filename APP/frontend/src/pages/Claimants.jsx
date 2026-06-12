import { useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import {
  PlusIcon,
  TrashIcon,
  PencilSimpleIcon,
  CheckCircleIcon,
  EnvelopeSimpleIcon,
  PaperPlaneTiltIcon,
  UserCircleIcon,
} from "@phosphor-icons/react";

const blank = () => ({
  label: "",
  first_name: "",
  last_name: "",
  middle_initial: "",
  claimant_id_last4: "",
  address: "",
  city: "",
  state: "IL",
  zip_code: "",
  phone: "",
  occupation: "",
  reminders_enabled: true,
  reminder_email: "",
  sms_enabled: true,
  sms_phone: "+14423321758",
  sms_verified: true,
});

export default function Claimants() {
  const { claimants, activeClaimantId, refreshClaimants, setActiveClaimant } =
    useAuth();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(blank());
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    refreshClaimants();
  }, [refreshClaimants]);

  const openNew = () => {
    setEditing(null);
    setForm(blank());
    setOpen(true);
  };
  const openEdit = (c) => {
    setEditing(c);
    setForm({ ...blank(), ...c });
    setOpen(true);
  };

  const save = async () => {
    setBusy(true);
    try {
      if (editing) {
        await api.put(`/claimants/${editing.id}`, form);
        toast.success("Claimant updated");
      } else {
        await api.post("/claimants", form);
        toast.success("Claimant created");
      }
      setOpen(false);
      await refreshClaimants();
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id) => {
    try {
      await api.delete(`/claimants/${id}`);
      toast.success("Claimant deleted");
      await refreshClaimants();
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };

  const makeActive = async (id) => {
    try {
      await setActiveClaimant(id);
      toast.success("Active claimant switched");
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };

  const sendTest = async (kind) => {
    try {
      const { data } = await api.post(`/reminders/test?kind=${kind}`);
      toast.success(`Sent ${data.sent} reminder email(s)`);
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };

  // OTP verification flow
  const [otpClaimant, setOtpClaimant] = useState(null);
  const [otpPhone, setOtpPhone] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [otpStep, setOtpStep] = useState(0); // 0 closed, 1 send, 2 verify
  const [otpBusy, setOtpBusy] = useState(false);

  const openOtp = (c) => {
    setOtpClaimant(c);
    setOtpPhone(c.sms_phone || "");
    setOtpCode("");
    setOtpStep(1);
  };
  const sendOtp = async () => {
    setOtpBusy(true);
    try {
      await api.post("/sms/send-otp", {
        claimant_id: otpClaimant.id,
        phone: otpPhone,
      });
      toast.success(`Code sent to ${otpPhone}`);
      setOtpStep(2);
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setOtpBusy(false);
    }
  };
  const verifyOtp = async () => {
    setOtpBusy(true);
    try {
      await api.post("/sms/verify-otp", {
        claimant_id: otpClaimant.id,
        code: otpCode,
      });
      toast.success("Phone verified — SMS reminders enabled");
      setOtpStep(0);
      await refreshClaimants();
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setOtpBusy(false);
    }
  };

  return (
    <div className="space-y-6" data-testid="claimants-page">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="kbd-label">Identities</div>
          <h1 className="font-display font-black text-4xl tracking-tighter mt-1">
            Claimants
          </h1>
          <p className="text-sm text-zinc-600 mt-2 max-w-2xl">
            Manage one or more claimant profiles. Each claimant has its own
            benefit weeks, work-search contacts, and reminders.
          </p>
        </div>
        <div className="flex gap-2">
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button
                className="rounded-none bg-[#0033A0] hover:bg-[#002266]"
                onClick={openNew}
                data-testid="new-claimant-button"
              >
                <PlusIcon size={16} weight="bold" className="mr-2" /> New
                Claimant
              </Button>
            </DialogTrigger>
            <DialogContent
              className="rounded-none max-w-2xl"
              data-testid="claimant-dialog"
            >
              <DialogHeader>
                <DialogTitle className="font-display tracking-tight">
                  {editing ? "Edit Claimant" : "New Claimant"}
                </DialogTitle>
              </DialogHeader>
              <div className="grid grid-cols-12 gap-3">
                <div className="col-span-12">
                  <Label className="kbd-label">
                    Display Label (e.g. "Self", "Spouse")
                  </Label>
                  <Input
                    value={form.label}
                    onChange={(e) =>
                      setForm({ ...form, label: e.target.value })
                    }
                    className="rounded-none mt-2"
                    data-testid="claimant-label-input"
                  />
                </div>
                <div className="col-span-5">
                  <Label className="kbd-label">First Name</Label>
                  <Input
                    value={form.first_name}
                    onChange={(e) =>
                      setForm({ ...form, first_name: e.target.value })
                    }
                    className="rounded-none mt-2"
                  />
                </div>
                <div className="col-span-2">
                  <Label className="kbd-label">MI</Label>
                  <Input
                    value={form.middle_initial}
                    onChange={(e) =>
                      setForm({ ...form, middle_initial: e.target.value })
                    }
                    className="rounded-none mt-2"
                  />
                </div>
                <div className="col-span-5">
                  <Label className="kbd-label">Last Name</Label>
                  <Input
                    value={form.last_name}
                    onChange={(e) =>
                      setForm({ ...form, last_name: e.target.value })
                    }
                    className="rounded-none mt-2"
                  />
                </div>
                <div className="col-span-6">
                  <Label className="kbd-label">Claimant ID (last 4)</Label>
                  <Input
                    value={form.claimant_id_last4}
                    onChange={(e) =>
                      setForm({ ...form, claimant_id_last4: e.target.value })
                    }
                    className="rounded-none mt-2"
                  />
                </div>
                <div className="col-span-6">
                  <Label className="kbd-label">Phone</Label>
                  <Input
                    value={form.phone}
                    onChange={(e) =>
                      setForm({ ...form, phone: e.target.value })
                    }
                    className="rounded-none mt-2"
                  />
                </div>
                <div className="col-span-12">
                  <Label className="kbd-label">Occupation</Label>
                  <Input
                    value={form.occupation}
                    onChange={(e) =>
                      setForm({ ...form, occupation: e.target.value })
                    }
                    className="rounded-none mt-2"
                  />
                </div>
                <div className="col-span-12">
                  <Label className="kbd-label">Address</Label>
                  <Input
                    value={form.address}
                    onChange={(e) =>
                      setForm({ ...form, address: e.target.value })
                    }
                    className="rounded-none mt-2"
                  />
                </div>
                <div className="col-span-6">
                  <Label className="kbd-label">City</Label>
                  <Input
                    value={form.city}
                    onChange={(e) => setForm({ ...form, city: e.target.value })}
                    className="rounded-none mt-2"
                  />
                </div>
                <div className="col-span-3">
                  <Label className="kbd-label">State</Label>
                  <Input
                    value={form.state}
                    onChange={(e) =>
                      setForm({ ...form, state: e.target.value })
                    }
                    className="rounded-none mt-2"
                  />
                </div>
                <div className="col-span-3">
                  <Label className="kbd-label">ZIP</Label>
                  <Input
                    value={form.zip_code}
                    onChange={(e) =>
                      setForm({ ...form, zip_code: e.target.value })
                    }
                    className="rounded-none mt-2"
                  />
                </div>
                <div className="col-span-12 border-t pt-3 mt-2">
                  <Label className="kbd-label">
                    <EnvelopeSimpleIcon
                      size={14}
                      weight="bold"
                      className="inline mr-1"
                    />
                    Reminder Email (leave blank to use account email)
                  </Label>
                  <Input
                    value={form.reminder_email}
                    onChange={(e) =>
                      setForm({ ...form, reminder_email: e.target.value })
                    }
                    placeholder="yourname@email.com"
                    className="rounded-none mt-2"
                    data-testid="claimant-reminder-email"
                  />
                  <label className="flex items-center gap-2 text-sm mt-3">
                    <input
                      type="checkbox"
                      checked={form.reminders_enabled}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          reminders_enabled: e.target.checked,
                        })
                      }
                      data-testid="claimant-reminders-toggle"
                    />
                    Receive weekly email reminders (Sun, Wed, Fri, Sat 9 AM CT)
                  </label>
                </div>
                <div className="col-span-12 border-t pt-3 mt-2">
                  <Label className="kbd-label">
                    SMS Phone (E.164 format, e.g. +13125550100)
                  </Label>
                  <Input
                    value={form.sms_phone}
                    onChange={(e) =>
                      setForm({ ...form, sms_phone: e.target.value })
                    }
                    placeholder="+13125550100"
                    className="rounded-none mt-2"
                    data-testid="claimant-sms-phone"
                  />
                  <label className="flex items-center gap-2 text-sm mt-3">
                    <input
                      type="checkbox"
                      checked={form.sms_enabled}
                      onChange={(e) =>
                        setForm({ ...form, sms_enabled: e.target.checked })
                      }
                      data-testid="claimant-sms-toggle"
                    />
                    Also send SMS reminders via Twilio
                  </label>
                  <p className="text-xs text-zinc-500 mt-2">
                    Standard message rates may apply. SMS is sent alongside
                    email reminders.
                  </p>
                </div>
              </div>
              <DialogFooter>
                <Button
                  variant="outline"
                  className="rounded-none"
                  onClick={() => setOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  className="rounded-none bg-[#0033A0] hover:bg-[#002266]"
                  onClick={save}
                  disabled={busy}
                  data-testid="claimant-save-button"
                >
                  {busy ? "Saving..." : "Save Claimant"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {claimants.length === 0 && (
          <div className="col-span-2 border border-dashed border-zinc-300 p-12 text-center text-sm text-zinc-500">
            <UserCircleIcon
              size={48}
              weight="thin"
              className="mx-auto mb-2 text-zinc-400"
            />
            No claimants yet — create your first.
          </div>
        )}
        {claimants.map((c) => (
          <div
            key={c.id}
            className={`border bg-white p-6 ${c.id === activeClaimantId ? "border-[#0033A0] border-2" : "border-zinc-200"}`}
            data-testid={`claimant-card-${c.id}`}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-display font-bold text-xl tracking-tight">
                    {c.label || "Untitled"}
                  </h3>
                  {c.id === activeClaimantId && (
                    <span className="inline-flex items-center gap-1 text-xs font-bold text-[#0033A0]">
                      <CheckCircleIcon size={12} weight="fill" /> ACTIVE
                    </span>
                  )}
                </div>
                <div className="text-sm text-zinc-700 mt-1">
                  {c.first_name} {c.middle_initial} {c.last_name}
                </div>
                <div className="kbd-label mt-2">
                  ID •••{c.claimant_id_last4} · {c.phone || "—"}
                </div>
                <div className="text-xs text-zinc-500 mt-1">{c.occupation}</div>
                <div className="text-xs text-zinc-500 mt-1">
                  {c.address
                    ? `${c.address}, ${c.city}, ${c.state} ${c.zip_code}`
                    : "—"}
                </div>
                <div className="mt-3 flex items-center gap-2">
                  <span
                    className={`text-xs font-semibold uppercase tracking-wider px-2 py-0.5 border inline-flex items-center gap-1 ${c.reminders_enabled ? "border-[#16A34A] text-[#16A34A]" : "border-zinc-300 text-zinc-500"}`}
                  >
                    <EnvelopeSimpleIcon size={12} weight="bold" />
                    {c.reminders_enabled ? "Reminders ON" : "Reminders off"}
                  </span>
                  {c.sms_enabled && (
                    <span
                      className={`text-xs font-semibold uppercase tracking-wider px-2 py-0.5 border ${c.sms_verified ? "border-[#0033A0] text-[#0033A0]" : "border-[#EAB308] text-[#EAB308]"}`}
                    >
                      {c.sms_verified ? "SMS ✓" : "SMS unverified"}{" "}
                      {c.sms_phone || ""}
                    </span>
                  )}
                  {c.email_bounced && (
                    <span className="text-xs font-semibold uppercase tracking-wider px-2 py-0.5 border border-[#DC2626] text-[#DC2626]">
                      EMAIL BOUNCED
                    </span>
                  )}
                  <span className="text-xs text-zinc-500 inline-flex items-center gap-1">
                    <EnvelopeSimpleIcon size={12} className="text-zinc-400" />{" "}
                    {c.reminder_email || "via account email"}
                  </span>
                </div>
              </div>
              <div className="flex flex-col gap-1">
                {c.id !== activeClaimantId && (
                  <Button
                    size="sm"
                    className="rounded-none bg-[#0033A0] hover:bg-[#002266]"
                    onClick={() => makeActive(c.id)}
                    data-testid={`activate-${c.id}`}
                  >
                    Set Active
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  className="rounded-none border-zinc-300"
                  onClick={() => openEdit(c)}
                  data-testid={`edit-claimant-${c.id}`}
                >
                  <PencilSimpleIcon size={14} weight="bold" />
                </Button>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button
                      size="sm"
                      variant="outline"
                      className="rounded-none border-zinc-300 hover:bg-red-50 hover:text-[#DC2626]"
                      data-testid={`delete-claimant-${c.id}`}
                    >
                      <TrashIcon size={14} weight="bold" />
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent className="rounded-none">
                    <AlertDialogHeader>
                      <AlertDialogTitle>Delete claimant?</AlertDialogTitle>
                      <AlertDialogDescription>
                        This will permanently delete this claimant and{" "}
                        <b>all</b> their benefit weeks and contacts.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel className="rounded-none">
                        Cancel
                      </AlertDialogCancel>
                      <AlertDialogAction
                        className="rounded-none bg-[#DC2626] hover:bg-red-700"
                        onClick={() => remove(c.id)}
                      >
                        Delete
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </div>

            <div className="border-t mt-4 pt-3 flex flex-wrap gap-2">
              <span className="kbd-label">Send test:</span>
              {["sunday", "wednesday", "friday", "saturday"].map((k) => (
                <button
                  key={k}
                  onClick={() => sendTest(k)}
                  data-testid={`test-${k}-${c.id}`}
                  className="text-xs font-semibold uppercase tracking-wider border border-zinc-300 px-2 py-1 hover:border-[#0033A0] hover:text-[#0033A0] inline-flex items-center gap-1"
                >
                  <PaperPlaneTiltIcon size={11} weight="bold" /> {k.slice(0, 3)}
                </button>
              ))}
              {c.sms_enabled && !c.sms_verified && (
                <button
                  onClick={() => openOtp(c)}
                  data-testid={`verify-phone-${c.id}`}
                  className="text-xs font-semibold uppercase tracking-wider border border-[#EAB308] text-[#EAB308] bg-yellow-50 px-2 py-1 inline-flex items-center gap-1"
                >
                  Verify phone →
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* OTP Dialog */}
      <Dialog
        open={otpStep > 0}
        onOpenChange={(o) => {
          if (!o) setOtpStep(0);
        }}
      >
        <DialogContent className="rounded-none" data-testid="otp-dialog">
          <DialogHeader>
            <DialogTitle className="font-display tracking-tight">
              Verify SMS phone
            </DialogTitle>
          </DialogHeader>
          {otpStep === 1 && (
            <div className="space-y-3">
              <p className="text-sm text-zinc-600">
                Enter the phone in E.164 format. We'll text a 6-digit code.
              </p>
              <Input
                value={otpPhone}
                onChange={(e) => setOtpPhone(e.target.value)}
                placeholder="+13125550100"
                className="rounded-none"
                data-testid="otp-phone-input"
              />
              <Button
                onClick={sendOtp}
                disabled={otpBusy || !otpPhone.startsWith("+")}
                className="rounded-none bg-[#0033A0] hover:bg-[#002266] w-full"
                data-testid="otp-send-button"
              >
                {otpBusy ? "Sending..." : "Send code"}
              </Button>
              <p className="text-xs text-zinc-500">
                Twilio trial: the number must already be verified in the Twilio
                console.
              </p>
            </div>
          )}
          {otpStep === 2 && (
            <div className="space-y-3">
              <p className="text-sm text-zinc-700">
                Enter the 6-digit code we texted to <b>{otpPhone}</b>.
              </p>
              <Input
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ""))}
                maxLength={6}
                placeholder="123456"
                className="rounded-none font-mono tracking-widest text-center text-xl"
                data-testid="otp-code-input"
              />
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  className="rounded-none flex-1"
                  onClick={() => setOtpStep(1)}
                >
                  Back
                </Button>
                <Button
                  onClick={verifyOtp}
                  disabled={otpBusy || otpCode.length !== 6}
                  className="rounded-none bg-[#0033A0] hover:bg-[#002266] flex-1"
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
