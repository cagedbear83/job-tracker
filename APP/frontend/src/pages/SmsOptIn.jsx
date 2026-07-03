import { useState } from "react";
import { Link } from "react-router-dom";
import {
  DeviceMobile,
  CheckCircle,
  ShieldCheck,
  Bell,
  ArrowRight,
  Warning,
} from "@phosphor-icons/react";

export default function SmsOptIn() {
  const [agreed, setAgreed] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [phone, setPhone] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = () => {
    if (!phone.match(/^\+1\d{10}$/)) {
      setError(
        "Please enter a valid US phone number e.g. +13125551212",
      );
      return;
    }
    if (!agreed) {
      setError("Please check the consent box to continue.");
      return;
    }
    setError("");
    setSubmitted(true);
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Brand bar */}
      <div className="h-1 bg-[#0033A0]" />

      {/* Header */}
      <header className="border-b border-border bg-background">
        <div className="max-w-4xl mx-auto px-6 py-3 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-9 h-9 bg-[#0033A0] flex items-center justify-center text-white font-display font-black tracking-tight text-sm">
              IL
            </div>
            <div>
              <div className="font-display font-black text-base leading-none tracking-tight">
                Illinois UI Tracker
              </div>
              <div className="text-[10px] font-bold tracking-widest text-muted-foreground uppercase mt-1">
                Work Search Compliance
              </div>
            </div>
          </Link>
          <Link
            to="/login"
            className="text-sm font-semibold text-[#0033A0] dark:text-[#5a86ff] hover:underline"
          >
            Sign In
          </Link>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-6 py-16">
        {/* Icon + Title */}
        <div className="flex items-center gap-4 mb-8">
          <div className="w-14 h-14 bg-[#0033A0] flex items-center justify-center flex-shrink-0">
            <DeviceMobile size={28} weight="bold" className="text-white" />
          </div>
          <div>
            <p className="text-xs font-bold tracking-widest text-muted-foreground uppercase mb-1">
              SMS Reminders
            </p>
            <h1 className="font-display font-black text-3xl tracking-tight leading-none">
              Opt-In Consent
            </h1>
          </div>
        </div>

        {!submitted ? (
          <>
            {/* What you're signing up for */}
            <div className="border border-border p-6 mb-6">
              <h2 className="font-display font-bold text-lg tracking-tight mb-4">
                What you're signing up for
              </h2>
              <div className="space-y-4 text-sm text-foreground leading-relaxed">
                <p>
                  <strong>Illinois UI Job Search Tracker</strong> sends optional
                  SMS text message reminders to help you stay compliant with
                  Illinois IDES work-search requirements (minimum 3 contacts per
                  benefit week, Sunday–Saturday).
                </p>
                <div className="space-y-2">
                  <p className="font-semibold text-foreground">
                    You may receive messages like:
                  </p>
                  <div className="bg-muted border border-border p-3 font-mono text-xs space-y-2">
                    <p className="text-foreground">
                      [IL UI Tracker] Weekly Reminder: 0/3 contacts logged for
                      week Apr 19–Apr 25. Log 3 more by Saturday to stay
                      compliant and avoid a denial of benefits.
                    </p>
                    <p className="text-foreground">
                      [IL UI Tracker] Compliance Alert: Only 1/3 contacts logged
                      for week Apr 19–Apr 25. Log 2 more by Saturday to avoid a
                      denial of benefits.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Key details */}
            <div className="grid grid-cols-3 gap-3 mb-6">
              {[
                { icon: Bell, label: "Frequency", value: "1–3 per week" },
                {
                  icon: ShieldCheck,
                  label: "Opt-out anytime",
                  value: "Reply STOP",
                },
                {
                  icon: Warning,
                  label: "Standard rates",
                  value: "May apply",
                },
              ].map(({ icon: Icon, label, value }) => (
                <div
                  key={label}
                  className="border border-border p-4 text-center"
                >
                  <Icon
                    size={20}
                    weight="bold"
                    className="text-[#0033A0] dark:text-[#5a86ff] mx-auto mb-2"
                  />
                  <div className="text-xs font-bold tracking-widest text-muted-foreground uppercase">
                    {label}
                  </div>
                  <div className="text-sm font-semibold text-foreground mt-1">
                    {value}
                  </div>
                </div>
              ))}
            </div>

            {/* Phone input */}
            <div className="border border-border p-6 mb-6">
              <h2 className="font-display font-bold text-lg tracking-tight mb-4">
                Your Phone Number
              </h2>
              <p className="text-sm text-muted-foreground mb-3">
                Enter your US mobile number (e.g. +13125551212).
              </p>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+13125551212"
                className="w-full border border-border px-3 py-2 text-sm font-mono focus:outline-none focus:border-[#0033A0]"
              />
              <p className="text-xs text-muted-foreground mt-2">
                SMS reminders are optional. You can enable or disable them
                anytime from your claimant profile inside the app.
              </p>
            </div>

            {/* Consent checkbox */}
            <div className="border border-[#0033A0] bg-accent p-5 mb-6">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={agreed}
                  onChange={(e) => setAgreed(e.target.checked)}
                  className="mt-1 w-4 h-4 accent-[#0033A0] flex-shrink-0"
                />
                <span className="text-sm text-foreground leading-relaxed">
                  I agree to receive automated SMS text message reminders from
                  Illinois UI Job Search Tracker at the phone number provided
                  above. I understand that message and data rates may apply,
                  message frequency varies (typically 1–3 per week), and I can
                  opt out at any time by replying <strong>STOP</strong>. Reply{" "}
                  <strong>HELP</strong> for help. View our{" "}
                  <Link to="/privacy" className="text-[#0033A0] dark:text-[#5a86ff] underline">
                    Privacy Policy
                  </Link>{" "}
                  and{" "}
                  <Link to="/terms" className="text-[#0033A0] dark:text-[#5a86ff] underline">
                    Terms & Conditions
                  </Link>
                  .
                </span>
              </label>
            </div>

            {error && (
              <div className="bg-red-50 dark:bg-red-950/30 border border-red-200 text-red-700 dark:text-red-300 text-sm p-3 mb-4">
                {error}
              </div>
            )}

            <button
              type="button"
              onClick={handleSubmit}
              className="w-full bg-[#0033A0] text-white font-bold py-3 flex items-center justify-center gap-2 hover:bg-[#002880] transition-colors"
            >
              Confirm Opt-In <ArrowRight size={16} weight="bold" />
            </button>

            <p className="text-xs text-muted-foreground text-center mt-4">
              To complete SMS setup, log in to your account and enable reminders
              from your Claimant profile.
            </p>
          </>
        ) : (
          /* Success state */
          <div className="border border-border p-12 text-center">
            <CheckCircle 
              size={48}
              weight="fill"
              className="text-green-600 mx-auto mb-4"
            />
            <h2 className="font-display font-black text-2xl tracking-tight mb-2">
              You're opted in
            </h2>
            <p className="text-sm text-muted-foreground mb-2">
              Your consent has been recorded for{" "}
              <span className="font-mono font-semibold">{phone}</span>.
            </p>
            <p className="text-sm text-muted-foreground mb-8">
              To activate SMS reminders, log in and enable them from your
              Claimant profile. Reply <strong>STOP</strong> at any time to
              unsubscribe.
            </p>
            <Link
              to="/login"
              className="inline-flex items-center gap-2 bg-[#0033A0] text-white font-bold px-6 py-3 hover:bg-[#002880] transition-colors"
            >
              Log In to Your Account <ArrowRight size={16} weight="bold" />
            </Link>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-border mt-16">
        <div className="max-w-4xl mx-auto px-6 py-6 flex items-center justify-between text-xs text-muted-foreground">
          <span>
            © {new Date().getFullYear()} Illinois UI Job Search Tracker
          </span>
          <div className="flex gap-4">
            <Link to="/privacy" className="hover:text-foreground">
              Privacy Policy
            </Link>
            <Link to="/terms" className="hover:text-foreground">
              Terms & Conditions
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}