import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { marketingUrl } from "@/lib/site";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { ArrowRightIcon } from "@phosphor-icons/react";
import { PLAN_STORAGE_KEY } from "@/pages/SignUp";

function formatPhone(value) {
  const digits = value.replace(/\D/g, "").slice(0, 10);
  if (digits.length === 0) return "";
  if (digits.length < 4) return `(${digits}`;
  if (digits.length < 7) return `(${digits.slice(0, 3)}) ${digits.slice(3)}`;
  return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`;
}

// Small red asterisk for required-field labels.
function Req() {
  return <span className="text-destructive ml-0.5">*</span>;
}

const PLAN_LABELS = { free: "Free", pro: "Pro", caseworker: "Case Worker" };

/**
 * Claimant details, collected right after Clerk sign-up.
 *
 * These fields used to be part of the registration form, submitted in the same
 * request that created the account. Clerk's sign-up collects only an email and
 * a password, so profile capture became its own step — same fields, same
 * validation, posted to /auth/onboarding, which creates the claimant profile
 * and seeds certification events exactly as registration did.
 */
export default function Onboarding() {
  const navigate = useNavigate();
  const { user, refreshUser } = useAuth();
  const [searchParams] = useSearchParams();

  // The plan is normally handed over in sessionStorage, because Clerk's
  // post-signup redirect drops query params (see SignUp.jsx). The ?plan=
  // fallback covers arriving here directly.
  const [selectedPlan, setSelectedPlan] = useState(null);
  useEffect(() => {
    let plan = searchParams.get("plan");
    if (!PLAN_LABELS[plan]) {
      try {
        plan = sessionStorage.getItem(PLAN_STORAGE_KEY);
      } catch {
        plan = null;
      }
    }
    setSelectedPlan(PLAN_LABELS[plan] ? plan : null);
  }, [searchParams]);

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [smsOptIn, setSmsOptIn] = useState(false);
  const [dob, setDob] = useState("");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [zip, setZip] = useState("");
  const [claimantId, setClaimantId] = useState("");
  const [knowsNextCertDate, setKnowsNextCertDate] = useState("na");
  const [nextCertDate, setNextCertDate] = useState("");
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/auth/onboarding", {
        first_name: firstName,
        last_name: lastName,
        phone,
        sms_opt_in: smsOptIn,
        dob,
        address,
        city,
        zip,
        claimant_id: claimantId || null,
        knows_next_cert_date: knowsNextCertDate,
        next_certification_date:
          knowsNextCertDate === "yes" ? nextCertDate : null,
      });
      // Pick up needs_onboarding: false before routing, so the guard in
      // App.jsx doesn't bounce us straight back here.
      try {
        sessionStorage.removeItem(PLAN_STORAGE_KEY);
      } catch {
        // nothing to clean up
      }
      await refreshUser();
      toast.success("Profile saved");
      navigate("/dashboard", { replace: true });
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  const inputClass = "rounded-none border-border mt-2";

  return (
    <div className="flex-1 bg-background">
      <div className="max-w-2xl mx-auto px-6 py-12">
        <div className="brand-bar w-20 mb-4" />
        <div className="kbd-label">Step 2 of 2</div>
        <h1 className="font-display font-black text-3xl tracking-tighter mt-1">
          Tell us about your claim
        </h1>
        <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
          {user?.name ? `Thanks, ${user.name.split(" ")[0]}. ` : ""}
          These details go on your ADJ034F work-search reports, so IDES sees the
          same information you filed with them.
        </p>

        {selectedPlan && (
          <p
            className="mt-4 border border-border bg-secondary px-3 py-2 text-sm"
            data-testid="selected-plan"
          >
            Signing up for{" "}
            <strong className="font-semibold">{PLAN_LABELS[selectedPlan]}</strong>.
          </p>
        )}

        <form onSubmit={onSubmit} className="mt-8 space-y-6" data-testid="onboarding-form">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <Label className="kbd-label">
                First Name
                <Req />
              </Label>
              <Input
                required
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                className={inputClass}
                data-testid="onboarding-firstName-input"
              />
            </div>
            <div>
              <Label className="kbd-label">
                Last Name
                <Req />
              </Label>
              <Input
                required
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                className={inputClass}
                data-testid="onboarding-lastName-input"
              />
            </div>
          </div>

          <div>
            <Label className="kbd-label">
              Phone
              <Req />
            </Label>
            <Input
              type="tel"
              required
              value={phone}
              onChange={(e) => setPhone(formatPhone(e.target.value))}
              placeholder="(312) 555-5555"
              className={inputClass}
              data-testid="onboarding-phone-input"
            />
            <label className="flex items-start gap-2 mt-3 text-xs text-muted-foreground leading-relaxed cursor-pointer">
              <input
                type="checkbox"
                checked={smsOptIn}
                onChange={(e) => setSmsOptIn(e.target.checked)}
                className="mt-0.5 w-4 h-4 accent-primary flex-shrink-0"
                data-testid="onboarding-sms-optin-checkbox"
              />
              <span>
                I agree to receive automated SMS text message reminders from
                Illinois UI Job Search Tracker at the phone number provided
                above. Message frequency varies. Message and data rates may
                apply. Reply <strong>STOP</strong> to cancel,{" "}
                <strong>HELP</strong> for help. See our{" "}
                <a
                  href={marketingUrl("/privacy")}
                  className="text-primary underline"
                  target="_blank"
                  rel="noreferrer"
                >
                  Privacy Policy
                </a>{" "}
                and{" "}
                <a
                  href={marketingUrl("/terms")}
                  className="text-primary underline"
                  target="_blank"
                  rel="noreferrer"
                >
                  Terms &amp; Conditions
                </a>
                . This is optional and not required to create an account.
              </span>
            </label>
          </div>

          <div>
            <Label className="kbd-label">
              Date of Birth
              <Req />
            </Label>
            <Input
              type="date"
              required
              value={dob}
              onChange={(e) => setDob(e.target.value)}
              className={inputClass}
              data-testid="onboarding-dob-input"
            />
          </div>

          <div>
            <Label className="kbd-label">
              Street Address
              <Req />
            </Label>
            <Input
              required
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              className={inputClass}
              data-testid="onboarding-address-input"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <Label className="kbd-label">
                City
                <Req />
              </Label>
              <Input
                required
                value={city}
                onChange={(e) => setCity(e.target.value)}
                className={inputClass}
                data-testid="onboarding-city-input"
              />
            </div>
            <div>
              <Label className="kbd-label">
                ZIP
                <Req />
              </Label>
              <Input
                required
                value={zip}
                onChange={(e) => setZip(e.target.value)}
                className={inputClass}
                data-testid="onboarding-zip-input"
              />
            </div>
          </div>

          <div>
            <Label className="kbd-label">Claimant ID</Label>
            <Input
              value={claimantId}
              onChange={(e) => setClaimantId(e.target.value)}
              placeholder="Optional — from your IDES correspondence"
              className={inputClass}
              data-testid="onboarding-claimantId-input"
            />
          </div>

          <div className="border border-border p-4">
            <Label className="kbd-label">
              Do you know your next certification date?
            </Label>
            <div className="flex flex-wrap gap-4 mt-3">
              {[
                { v: "yes", label: "Yes" },
                { v: "no", label: "No" },
                { v: "na", label: "Not sure" },
              ].map((opt) => (
                <label
                  key={opt.v}
                  className="flex items-center gap-2 text-sm cursor-pointer"
                >
                  <input
                    type="radio"
                    name="knowsNextCertDate"
                    value={opt.v}
                    checked={knowsNextCertDate === opt.v}
                    onChange={(e) => setKnowsNextCertDate(e.target.value)}
                    className="w-4 h-4 accent-primary"
                  />
                  {opt.label}
                </label>
              ))}
            </div>
            {knowsNextCertDate === "yes" && (
              <div className="mt-4">
                <Label className="kbd-label">Next certification date</Label>
                <Input
                  type="date"
                  required
                  value={nextCertDate}
                  onChange={(e) => setNextCertDate(e.target.value)}
                  className={inputClass}
                  data-testid="onboarding-certDate-input"
                />
                <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
                  We'll add the next 26 bi-weekly certification dates to your
                  calendar so you don't have to enter them one by one.
                </p>
              </div>
            )}
          </div>

          <Button
            type="submit"
            disabled={busy}
            className="rounded-none bg-primary hover:bg-primary-hover h-12 px-6 font-semibold w-full"
            data-testid="onboarding-submit"
          >
            {busy ? "Saving…" : "Finish setup"}
            {!busy && (
              <ArrowRightIcon size={16} weight="bold" className="ml-2" />
            )}
          </Button>
        </form>
      </div>
    </div>
  );
}
