import { useState } from "react";
import Logo from "@/components/Logo";
import { site, marketingUrl } from "@/lib/site";
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
      <div className="brand-bar" />

      {/* Header */}
      <header className="border-b border-border bg-background">
        <div className="max-w-4xl mx-auto px-6 py-3 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <Logo size={32} showWordmark={false} />
            <div>
              <div className="font-display font-black text-base leading-none tracking-tight">
                {site.name}
              </div>
              <div className="kbd-label mt-1">
                Work Search Compliance
              </div>
            </div>
          </Link>
          <Link
            to="/sign-in"
            className="text-sm font-semibold text-primary hover:underline"
          >
            Sign In
          </Link>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-6 py-16">
        {/* Icon + Title */}
        <div className="flex items-center gap-4 mb-8">
          <div className="w-14 h-14 bg-primary flex items-center justify-center flex-shrink-0">
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
                  <div className="bg-secondary border border-border p-3 font-mono text-xs space-y-2">
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
                    className="text-primary mx-auto mb-2"
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
                className="w-full border border-border px-3 py-2 text-sm font-mono focus:outline-none focus:border-primary"
              />
              <p className="text-xs text-muted-foreground mt-2">
                SMS reminders are optional. You can enable or disable them
                anytime from your claimant profile inside the app.
              </p>
            </div>

            {/* Consent checkbox */}
            <div className="border border-primary bg-[#f0f4ff] p-5 mb-6">
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
                  <a href={marketingUrl("/privacy")} className="text-primary underline">
                    Privacy Policy
                  </a>{" "}
                  and{" "}
                  <a href={marketingUrl("/terms")} className="text-primary underline">
                    Terms & Conditions
                  </a>
                  .
                </span>
              </label>
            </div>

            {error && (
              <div className="bg-destructive/10 border border-destructive/30 text-destructive text-sm p-3 mb-4">
                {error}
              </div>
            )}

            <button
              type="button"
              onClick={handleSubmit}
              className="w-full bg-primary text-white font-bold py-3 flex items-center justify-center gap-2 hover:bg-primary/90 transition-colors"
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
              className="text-[#16A34A] mx-auto mb-4"
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
              to="/sign-in"
              className="inline-flex items-center gap-2 bg-primary text-white font-bold px-6 py-3 hover:bg-primary/90 transition-colors"
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
            © {new Date().getFullYear()} {site.company}
          </span>
          <div className="flex gap-4">
            <a href={marketingUrl("/privacy")} className="hover:text-foreground">
              Privacy Policy
            </a>
            <a href={marketingUrl("/terms")} className="hover:text-foreground">
              Terms & Conditions
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
