import { useState, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
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
    return { score: 0, label: "Too common — this password has been breached", color: "text-red-500" };
  }
  if (emailLocal && lower.includes(emailLocal) && emailLocal.length > 2) {
    return { score: 0, label: "Password cannot contain your email address", color: "text-red-500" };
  }
  if (namePart && lower.includes(namePart) && namePart.length > 2) {
    return { score: 0, label: "Password cannot contain your name", color: "text-red-500" };
  }
  if (lower.includes("illinoisjobtracker") || lower.includes("iltracker")) {
    return { score: 0, label: "Password cannot contain the site name", color: "text-red-500" };
  }

  // Length is the primary entropy driver (NIST SP 800-63B)
  const len = password.length;
  if (len < 12) return { score: 1, label: "Too short — minimum 12 characters", color: "text-red-500" };

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
  return { score: 5, label: "Very strong", color: "text-green-600" };
}

const STRENGTH_BARS = [
  { min: 1, active: "bg-red-500" },
  { min: 2, active: "bg-orange-500" },
  { min: 3, active: "bg-yellow-500" },
  { min: 4, active: "bg-green-500" },
  { min: 5, active: "bg-green-600" },
];

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [dob, setDob] = useState("");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [zip, setZip] = useState("");
  const [claimantId, setClaimantId] = useState("");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [busy, setBusy] = useState(false);

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
  const canSubmit = passwordReady && passwordsMatch && !busy;

  const onSubmit = async (e) => {
    e.preventDefault();
    if (!passwordReady) {
      toast.error(strength.label || "Password does not meet requirements.");
      return;
    }
    if (!passwordsMatch) {
      toast.error("Passwords do not match.");
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
        dob: dob,
        address: address,
        city: city,
        zip: zip,
        claimant_id: claimantId,
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
    <div className="min-h-screen flex items-center justify-center bg-background p-8">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-md space-y-6"
        data-testid="register-form"
      >
        <div>
          <div className="brand-bar w-20 mb-4" />
          <div className="kbd-label">New Account</div>
          <h2 className="font-display font-black text-3xl tracking-tighter mt-1 text-foreground">
            Register
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Already have an account?{" "}
            <Link
              to="/login"
              className="text-[#0033A0] dark:text-[#5a86ff] font-semibold underline"
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
              <Label className="kbd-label">First Name</Label>
              <Input
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                className="rounded-none border-border mt-2"
                data-testid="register-firstName-input"
              />
            </div>
            <div>
              <Label className="kbd-label">Last Name</Label>
              <Input
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                className="rounded-none border-border mt-2"
                data-testid="register-lastName-input"
              />
            </div>
          </div>
          <div>
            <Label className="kbd-label">Phone</Label>
            <Input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="(312) 555-5555"
              className="rounded-none border-border mt-2"
              data-testid="register-phone-input"
            />
          </div>
          <div>
            <Label className="kbd-label">Date of Birth</Label>
            <Input
              type="date"
              value={dob}
              onChange={(e) => setDob(e.target.value)}
              className="rounded-none border-border mt-2"
              data-testid="register-dob-input"
            />
          </div>
          <div>
            <Label className="kbd-label">Address</Label>
            <Input
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              className="rounded-none border-border mt-2"
              data-testid="register-address-input"
            />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <Label className="kbd-label">City</Label>
              <Input
                value={city}
                onChange={(e) => setCity(e.target.value)}
                className="rounded-none border-border mt-2"
                data-testid="register-city-input"
              />
            </div>
            <div>
              <Label className="kbd-label">ZIP</Label>
              <Input
                value={zip}
                onChange={(e) => setZip(e.target.value)}
                className="rounded-none border-border mt-2"
                data-testid="register-zip-input"
              />
            </div>
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
            <Label className="kbd-label">Email</Label>
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
            <Label className="kbd-label">Password</Label>
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
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
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
                        strength.score >= bar.min ? bar.active : "bg-muted"
                      }`}
                    />
                  ))}
                </div>
                <p className={`text-xs font-medium ${strength.color}`}>
                  {strength.label}
                </p>
                {passwordTooLong && (
                  <p className="text-xs text-red-500">
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
            <Label className="kbd-label">Confirm Password</Label>
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
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                aria-label={showConfirm ? "Hide password" : "Show password"}
              >
                {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {confirmPassword.length > 0 && !passwordsMatch && (
              <p className="text-xs text-red-500 mt-1">Passwords do not match.</p>
            )}
            {confirmPassword.length > 0 && passwordsMatch && (
              <p className="text-xs text-green-600 mt-1">✓ Passwords match.</p>
            )}
          </div>
        </div>

        <Button
          type="submit"
          disabled={!canSubmit}
          className="w-full rounded-none bg-[#0033A0] hover:bg-[#002266] text-white h-11 font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
          data-testid="register-submit-button"
        >
          {busy ? "Creating account..." : "Create account"}
        </Button>
      </form>
    </div>
  );
}