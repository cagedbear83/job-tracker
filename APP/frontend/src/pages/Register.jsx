import { useState, useMemo } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { marketingUrl } from "@/lib/site";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Eye, EyeOff } from "lucide-react";

// A sample of the most common breached passwords.
// For production, consider a full blocklist like the "Have I Been Pwned" top 100k.
const COMMON_PASSWORDS = new Set([
  "password", "123456", "12345678", "1234567890", "password1", "password123",
  "iloveyou", "admin", "welcome", "monkey", "dragon", "master", "letmein",
  "sunshine", "princess", "football", "shadow", "superman", "michael",
  "qwerty", "qwerty123", "abc123", "pass", "test", "hello", "welcome1",
  "passw0rd", "pa$$word", "p@ssword", "p@$$w0rd", "trustno1", "baseball",
]);

function getPasswordStrength(password, email, name) {
  if (!password) return { score: 0, label: "", color: "" };

  const lower = password.toLowerCase();
  const emailLocal = email ? email.split("@")[0].toLowerCase() : "";
  const namePart = name ? name.toLowerCase().replace(/\s+/g, "") : "";

  // Blocklist checks
  if (COMMON_PASSWORDS.has(lower)) {
    return { score: 0, label: "Too common — this password has been breached", color: "text-destructive" };
  }
  if (emailLocal && lower.includes(emailLocal) && emailLocal.length > 2) {
    return { score: 0, label: "Password cannot contain your email address", color: "text-destructive" };
  }
  if (namePart && lower.includes(namePart) && namePart.length > 2) {
    return { score: 0, label: "Password cannot contain your name", color: "text-destructive" };
  }
  if (lower.includes("illinoisjobtracker") || lower.includes("iltracker")) {
    return { score: 0, label: "Password cannot contain the site name", color: "text-destructive" };
  }

  // Length is the primary entropy driver (NIST SP 800-63B)
  const len = password.length;
  if (len < 12) return { score: 1, label: "Too short — minimum 12 characters", color: "text-destructive" };

  // Score based on length + character variety (entropy proxy)
  let score = 0;
  if (len >= 12) score += 1;
  if (len >= 16) score += 1;
  if (len >= 20) score += 1;
  if (/[A-Z]/.test(password)) score += 0.5;
  if (/[0-9]/.test(password)) score += 0.5;
  if (/[^A-Za-z0-9]/.test(password)) score += 0.5;
  if (/\s/.test(password)) score += 0.5; // passphrase bonus

  if (score <= 1.5) return { score: 2, label: "Weak", color: "text-orange-500" };
  if (score <= 2.5) return { score: 3, label: "Fair", color: "text-yellow-500" };
  if (score <= 3.5) return { score: 4, label: "Strong", color: "text-green-500" };
  return { score: 5, label: "Very strong", color: "text-[#16A34A]" };
}

const STRENGTH_BARS = [
  { min: 1, active: "bg-red-500" },
  { min: 2, active: "bg-orange-500" },
  { min: 3, active: "bg-yellow-500" },
  { min: 4, active: "bg-green-500" },
  { min: 5, active: "bg-[#16A34A]" },
];

// Formats a phone number as the user types: (XXX) XXX-XXXX. Strips
// everything but digits first so pasted/partial input (dashes, spaces,
// a leading "1") doesn't break the mask, and caps at 10 digits.
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

// The pricing page on illinoisjobtracker.com deep-links here as
// /register?plan=pro and ?plan=caseworker. Without this the visitor picked a
// plan, crossed domains, and landed on a form that had never heard of it.
const PLAN_LABELS = {
  free: "Free",
  pro: "Pro",
  caseworker: "Case Worker",
};

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [smsOptIn, setSmsOptIn] = useState(false);
  const [dob, setDob] = useState("");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [zip, setZip] = useState("");
  const [claimantId, setClaimantId] = useState("");
  // "Do you know your next certification date?" — silently seeds 26
  // bi-weekly certification events on the Calendar when answered "yes".
  const [knowsNextCertDate, setKnowsNextCertDate] = useState("na");
  const [nextCertDate, setNextCertDate] = useState("");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [searchParams] = useSearchParams();
  const selectedPlan = PLAN_LABELS[searchParams.get("plan")] ? searchParams.get("plan") : null;

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const strength = useMemo(
    () => getPasswordStrength(form.password, form.email, form.name),
    [form.password, form.email, form.name]
  );

  const passwordTooLong = form.password.length > 64;
  const passwordReady = form.password.length >= 12 && strength.score >= 2 && !passwordTooLong;
  const passwordsMatch = form.password === confirmPassword;

  const REQUIRED_FIELDS = [
    [firstName, "First Name"],
    [lastName, "Last Name"],
    [phone, "Phone"],
    [dob, "Date of Birth"],
    [address, "Address"],
    [city, "City"],
    [zip, "ZIP"],
  ];
  const requiredFieldsFilled = REQUIRED_FIELDS.every(([val]) => val && val.trim().length > 0);
  const certDateOk = knowsNextCertDate !== "yes" || nextCertDate.trim().length > 0;

  const canSubmit =
    passwordReady && passwordsMatch && requiredFieldsFilled && certDateOk && !busy;

  const onSubmit = async (e) => {
    e.preventDefault();
    for (const [val, label] of REQUIRED_FIELDS) {
      if (!val || !val.trim()) {
        toast.error(`${label} is required.`);
        return;
      }
    }
    if (!passwordReady) {
      toast.error(strength.label || "Password does not meet requirements.");
      return;
    }
    if (!passwordsMatch) {
      toast.error("Passwords do not match.");
      return;
    }
    if (!certDateOk) {
      toast.error("Enter your next certification date, or choose No / N/A.");
      return;
    }
    setBusy(true);
    try {
      await register({
        email: form.email,
        password: form.password,
        name: form.name,
        first_name: firstName,
        last_name: lastName,
        phone: phone,
        sms_opt_in: smsOptIn,
        dob: dob,
        address: address,
        city: city,
        zip: zip,
        claimant_id: claimantId,
        knows_next_cert_date: knowsNextCertDate,
        next_certification_date: knowsNextCertDate === "yes" ? nextCertDate : null,
      });
      toast.success("Account created. Please verify your email.");
      navigate("/login");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex-1 grid grid-cols-1 md:grid-cols-2 bg-background">
      <div className="hidden md:block relative bg-primary">
        <div className="absolute inset-0 p-12 flex flex-col justify-between text-white">
          <div className="brand-bar w-32" />
          <div>
            <div className="kbd-label text-white/70">State of Illinois</div>
            <h1 className="font-display font-black text-5xl lg:text-6xl tracking-tighter mt-2">
              Job Search<br />Tracker
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
      <form
        onSubmit={onSubmit}
        className="w-full max-w-md space-y-6"
        data-testid="register-form"
      >
        <div className="md:hidden">
          <div className="brand-bar w-20 mb-4" />
        </div>
        <div>
          <div className="kbd-label">New Account</div>
          <h2 className="font-display font-black text-3xl tracking-tighter mt-1">
            Register
          </h2>
          {selectedPlan && (
            <p
              className="mt-2 border border-border bg-secondary px-3 py-2 text-sm"
              data-testid="selected-plan"
            >
              Signing up for{" "}
              <strong className="font-semibold">
                {PLAN_LABELS[selectedPlan]}
              </strong>
              .{" "}
              <a
                href={marketingUrl("/pricing")}
                className="text-primary underline"
              >
                Compare plans
              </a>
            </p>
          )}
          <p className="text-sm text-muted-foreground mt-1">
            Already have an account?{" "}
            <Link
              to="/login"
              className="text-primary font-semibold underline"
              data-testid="link-login"
            >
              Sign in
            </Link>
          </p>
        </div>

        {/* Personal Info */}
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="kbd-label">First Name<Req /></Label>
              <Input
                required
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                className="rounded-none border-border mt-2"
                data-testid="register-firstName-input"
              />
            </div>
            <div>
              <Label className="kbd-label">Last Name<Req /></Label>
              <Input
                required
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                className="rounded-none border-border mt-2"
                data-testid="register-lastName-input"
              />
            </div>
          </div>
          <div>
            <Label className="kbd-label">Phone<Req /></Label>
            <Input
              type="tel"
              required
              value={phone}
              onChange={(e) => setPhone(formatPhone(e.target.value))}
              placeholder="(312) 555-5555"
              className="rounded-none border-border mt-2"
              data-testid="register-phone-input"
            />
            <label className="flex items-start gap-2 mt-3 text-xs text-muted-foreground leading-relaxed cursor-pointer">
              <input
                type="checkbox"
                checked={smsOptIn}
                onChange={(e) => setSmsOptIn(e.target.checked)}
                className="mt-0.5 w-4 h-4 accent-primary flex-shrink-0"
                data-testid="register-sms-optin-checkbox"
              />
              <span>
                I agree to receive automated SMS text message reminders from
                Illinois UI Job Search Tracker at the phone number provided
                above. Message frequency varies. Message and data rates may
                apply. Reply <strong>STOP</strong> to cancel, <strong>HELP</strong>{" "}
                for help. See our{" "}
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
            <Label className="kbd-label">Date of Birth<Req /></Label>
            <Input
              type="date"
              required
              value={dob}
              onChange={(e) => setDob(e.target.value)}
              className="rounded-none border-border mt-2"
              data-testid="register-dob-input"
            />
          </div>
          <div>
            <Label className="kbd-label">Address<Req /></Label>
            <Input
              required
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              className="rounded-none border-border mt-2"
              data-testid="register-address-input"
            />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <Label className="kbd-label">City<Req /></Label>
              <Input
                required
                value={city}
                onChange={(e) => setCity(e.target.value)}
                className="rounded-none border-border mt-2"
                data-testid="register-city-input"
              />
            </div>
            <div>
              <Label className="kbd-label">ZIP<Req /></Label>
              <Input
                required
                value={zip}
                onChange={(e) => setZip(e.target.value)}
                className="rounded-none border-border mt-2"
                data-testid="register-zip-input"
              />
            </div>
          </div>

          {/* Certification-date question — answering "yes" silently seeds 26
              bi-weekly certification events on the Calendar (see backend
              _seed_certification_events), so a claimant's certification
              deadlines show up automatically without adding each one by hand. */}
          <div>
            <Label className="kbd-label">Do you know your next certification date?</Label>
            <div className="flex gap-2 mt-2" role="radiogroup" aria-label="Do you know your next certification date?">
              {[
                { value: "yes", label: "Yes" },
                { value: "no", label: "No" },
                { value: "na", label: "N/A" },
              ].map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setKnowsNextCertDate(opt.value)}
                  aria-pressed={knowsNextCertDate === opt.value}
                  className={`flex-1 rounded-none border py-2 text-sm font-medium transition-colors ${
                    knowsNextCertDate === opt.value
                      ? "bg-primary text-white border-primary"
                      : "border-border text-muted-foreground hover:border-primary/50"
                  }`}
                  data-testid={`register-knowsCert-${opt.value}`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            {knowsNextCertDate === "yes" && (
              <div className="mt-3">
                <Label className="kbd-label">Next Certification Date<Req /></Label>
                <Input
                  type="date"
                  required
                  value={nextCertDate}
                  onChange={(e) => setNextCertDate(e.target.value)}
                  className="rounded-none border-border mt-2"
                  data-testid="register-nextCertDate-input"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  We'll add this and the next 25 bi-weekly certification dates to your Calendar automatically.
                </p>
              </div>
            )}
          </div>

          <div>
            <Label className="kbd-label">Illinois Claimant ID (Optional)</Label>
            <Input
              value={claimantId}
              onChange={(e) => setClaimantId(e.target.value)}
              placeholder="1234567"
              className="rounded-none border-border mt-2"
              data-testid="register-claimantId-input"
            />
          </div>
        </div>

        {/* Account Credentials */}
        <div className="space-y-3">
          <div>
            <Label className="kbd-label">Full Name</Label>
            <Input
              required
              name="name"
              value={form.name}
              onChange={handleInputChange}
              className="rounded-none border-border mt-2"
              data-testid="register-name-input"
            />
          </div>
          <div>
            <Label className="kbd-label">Email<Req /></Label>
            <Input
              type="email"
              required
              name="email"
              value={form.email}
              onChange={handleInputChange}
              className="rounded-none border-border mt-2"
              data-testid="register-email-input"
            />
          </div>

          {/* Password with show/hide */}
          <div>
            <Label className="kbd-label">Password<Req /></Label>
            <div className="relative mt-2">
              <Input
                type={showPassword ? "text" : "password"}
                required
                name="password"
                value={form.password}
                onChange={handleInputChange}
                className="rounded-none border-border pr-10"
                data-testid="register-password-input"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-muted-foreground"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>

            {/* Strength meter */}
            {form.password.length > 0 && (
              <div className="mt-2 space-y-1.5">
                <div className="flex gap-1">
                  {STRENGTH_BARS.map((bar, i) => (
                    <div
                      key={i}
                      className={`h-1 flex-1 rounded-full transition-colors duration-200 ${
                        strength.score >= bar.min ? bar.active : "bg-secondary"
                      }`}
                    />
                  ))}
                </div>
                <p className={`text-xs font-medium ${strength.color}`}>
                  {strength.label}
                </p>
                {passwordTooLong && (
                  <p className="text-xs text-destructive">
                    Maximum 64 characters allowed ({form.password.length}/64)
                  </p>
                )}
                {!passwordTooLong && form.password.length < 12 && (
                  <p className="text-xs text-muted-foreground">
                    {12 - form.password.length} more character{12 - form.password.length !== 1 ? "s" : ""} needed
                  </p>
                )}
                {form.password.length >= 12 && !passwordTooLong && strength.score >= 2 && (
                  <p className="text-xs text-muted-foreground">
                    Tip: longer passphrases (e.g. "lake sunrise coffee 42") are easier to remember and harder to crack.
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Confirm password with show/hide */}
          <div>
            <Label className="kbd-label">Confirm Password<Req /></Label>
            <div className="relative mt-2">
              <Input
                type={showConfirm ? "text" : "password"}
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className={`rounded-none pr-10 ${
                  confirmPassword.length > 0
                    ? passwordsMatch
                      ? "border-green-500"
                      : "border-red-400"
                    : "border-border"
                }`}
                data-testid="register-confirmPassword-input"
              />
              <button
                type="button"
                onClick={() => setShowConfirm((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-muted-foreground"
                aria-label={showConfirm ? "Hide password" : "Show password"}
              >
                {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {confirmPassword.length > 0 && !passwordsMatch && (
              <p className="text-xs text-destructive mt-1">Passwords do not match.</p>
            )}
            {confirmPassword.length > 0 && passwordsMatch && (
              <p className="text-xs text-[#16A34A] mt-1">✓ Passwords match.</p>
            )}
          </div>
        </div>

        <Button
          type="submit"
          disabled={!canSubmit}
          className="w-full rounded-none bg-primary hover:bg-primary/90 text-white h-11 font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
          data-testid="register-submit-button"
        >
          {busy ? "Creating account..." : "Create account"}
        </Button>
      </form>
      </div>
    </div>
  );
}