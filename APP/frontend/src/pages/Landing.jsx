import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  CheckCircleIcon,
  ShieldCheckIcon,
  RobotIcon,
  FileCsvIcon,
  FilePdfIcon,
  CalendarCheckIcon,
  EnvelopeSimpleIcon,
  DeviceMobileIcon,
  UsersThreeIcon,
  ArrowRightIcon,
} from "@phosphor-icons/react";

const Feature = ({ Icon, title, desc }) => (
  <div className="border border-border bg-card p-6">
    <Icon size={28} weight="bold" className="text-[#0033A0] dark:text-[#5a86ff]" />
    <h3 className="font-display font-bold text-lg tracking-tight mt-3 text-foreground">
      {title}
    </h3>
    <p className="text-sm text-muted-foreground mt-2 leading-relaxed">{desc}</p>
  </div>
);

export default function Landing() {
  return (
    <div className="min-h-screen bg-background">
      <div className="brand-bar" />
      <header className="border-b border-border bg-background">
        <div className="max-w-[1440px] mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-[#0033A0] flex items-center justify-center text-white font-display font-black tracking-tight">
              IL
            </div>
            <div>
              <div className="font-display font-black text-base leading-none tracking-tight text-foreground">
                Illinois UI Tracker
              </div>
              <div className="kbd-label mt-1">Work Search Compliance</div>
            </div>
          </div>
          <nav className="flex items-center gap-2">
            <Link to="/login">
              <Button
                variant="outline"
                className="rounded-none border-border text-foreground"
                data-testid="landing-signin-button"
              >
                Sign in
              </Button>
            </Link>
            <Link to="/register">
              <Button
                className="rounded-none bg-[#0033A0] hover:bg-[#002266] text-white"
                data-testid="landing-signup-button"
              >
                Get started
              </Button>
            </Link>
          </nav>
        </div>
      </header>

      <section className="border-b border-border">
        <div className="max-w-[1440px] mx-auto px-6 py-16 grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          <div>
            <div className="kbd-label">
              For Illinois Claimants & Case Workers
            </div>
            <h1 className="font-display font-black text-5xl sm:text-6xl tracking-tighter mt-3 leading-[1.05] text-foreground">
              Stay compliant.
              <br />
              <span className="text-[#0033A0] dark:text-[#5a86ff]">Get paid.</span>
            </h1>
            <p className="text-base text-foreground mt-5 max-w-xl leading-relaxed">
              Track every work-search contact, certify Sun–Sat benefit weeks,
              and generate official-style ADJ034F reports for IDES — backed by a
              full audit trail.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link to="/register">
                <Button
                  className="rounded-none bg-[#0033A0] hover:bg-[#002266] text-white h-12 px-6 font-semibold"
                  data-testid="hero-cta-signup"
                >
                  Create free account{" "}
                  <ArrowRightIcon size={16} weight="bold" className="ml-2" />
                </Button>
              </Link>
              <Link to="/login">
                <Button
                  variant="outline"
                  className="rounded-none border-border text-foreground h-12 px-6 font-semibold"
                  data-testid="hero-cta-signin"
                >
                  Have an invite? Sign in
                </Button>
              </Link>
            </div>
            <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <CheckCircleIcon
                  size={14}
                  weight="fill"
                  className="text-[#16A34A]"
                />{" "}
                Free for claimants
              </span>
              <span className="inline-flex items-center gap-1">
                <CheckCircleIcon
                  size={14}
                  weight="fill"
                  className="text-[#16A34A]"
                />{" "}
                No credit card
              </span>
              <span className="inline-flex items-center gap-1">
                <CheckCircleIcon
                  size={14}
                  weight="fill"
                  className="text-[#16A34A]"
                />{" "}
                ADJ034F-style PDFs
              </span>
            </div>
          </div>
          <div className="relative border border-border bg-card aspect-[4/3] overflow-hidden">
            <img
              src="https://images.unsplash.com/photo-1657639789999-837194c7d6aa?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA2MDV8MHwxfHNlYXJjaHwxfHxpbGxpbm9pcyUyMGNoaWNhZ28lMjBza3lsaW5lfGVufDB8fHx8MTc3ODU0ODUxN3ww&ixlib=rb-4.1.0&q=85"
              alt="Chicago skyline"
              className="w-full h-full object-cover"
            />
            <div className="absolute inset-0 bg-[#0033A0]/30" />
            <div className="absolute bottom-6 left-6 right-6 bg-card border border-border p-4">
              <div className="kbd-label">Active week</div>
              <div className="flex items-center justify-between mt-2">
                <div className="font-display font-bold text-xl tracking-tight text-foreground">
                  Apr 19 → Apr 25
                </div>
                <span className="inline-flex items-center gap-1 text-xs font-bold text-[#16A34A]">
                  <CheckCircleIcon size={14} weight="fill" /> COMPLIANT 4/3
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="border-b border-border">
        <div className="max-w-[1440px] mx-auto px-6 py-16">
          <div className="kbd-label">Built for Illinois UI Compliance</div>
          <h2 className="font-display font-bold text-3xl tracking-tight mt-2 text-foreground">
            Everything you need to stay certified
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-8">
            <Feature
              Icon={CalendarCheckIcon}
              title="Sun–Sat Benefit Weeks"
              desc="Auto-snap to Illinois' Sunday–Saturday week. ≥3 contacts enforced."
            />
            <Feature
              Icon={RobotIcon}
              title="AI Screenshot Import"
              desc="Drop an Indeed screenshot. Gemini 2.5 Pro extracts the job in seconds."
            />
            <Feature
              Icon={FileCsvIcon}
              title="CSV Import & Export"
              desc="Bulk-import from spreadsheets. Export per week or all contacts."
            />
            <Feature
              Icon={FilePdfIcon}
              title="ADJ034F-style PDF"
              desc="Generate IDES-style work-search reports with full audit-ready data."
            />
            <Feature
              Icon={EnvelopeSimpleIcon}
              title="Email + SMS Reminders"
              desc="Sun / Wed / Fri / Sat nudges via Mailgun + Twilio. Never miss a week."
            />
            <Feature
              Icon={UsersThreeIcon}
              title="Multi-claimant"
              desc="One account, multiple claimants. Family + case-worker friendly."
            />
            <Feature
              Icon={ShieldCheckIcon}
              title="Admin / Case-worker"
              desc="Read-only oversight across users. Invite claimants with one click."
            />
            <Feature
              Icon={DeviceMobileIcon}
              title="Mobile-friendly"
              desc="Drawer nav, dense data tables — works on a phone in the field."
            />
            <Feature
              Icon={CheckCircleIcon}
              title="Full audit trail"
              desc="Every edit captured with field-level old → new diffs."
            />
          </div>
        </div>
      </section>

      <section>
        <div className="max-w-[1440px] mx-auto px-6 py-16 grid grid-cols-1 lg:grid-cols-2 gap-12 items-start">
          <div>
            <div className="kbd-label">For Case Workers</div>
            <h2 className="font-display font-bold text-3xl tracking-tight mt-2 text-foreground">
              Invite a claimant in one click
            </h2>
            <p className="text-base text-foreground mt-4 leading-relaxed">
              Send a single-use signup link to anyone you're helping. They land
              on a pre-filled registration page with their claimant profile
              already created.
            </p>
            <Link
              to="/login"
              className="inline-flex items-center gap-2 text-[#0033A0] dark:text-[#5a86ff] font-semibold underline mt-4 text-sm"
            >
              Admin sign-in <ArrowRightIcon size={14} weight="bold" />
            </Link>
          </div>
          <div className="bg-muted border border-border p-6">
            <div className="kbd-label">Workflow</div>
            <ol className="mt-3 space-y-3 text-sm text-foreground">
              <li className="flex gap-3">
                <span className="w-6 h-6 bg-[#0033A0] text-white text-xs font-bold inline-flex items-center justify-center">
                  1
                </span>
                <span>
                  Admin opens <code>/admin</code> → Invites → enters claimant
                  email + label.
                </span>
              </li>
              <li className="flex gap-3">
                <span className="w-6 h-6 bg-[#0033A0] text-white text-xs font-bold inline-flex items-center justify-center">
                  2
                </span>
                <span>Mailgun emails a 14-day single-use signup link.</span>
              </li>
              <li className="flex gap-3">
                <span className="w-6 h-6 bg-[#0033A0] text-white text-xs font-bold inline-flex items-center justify-center">
                  3
                </span>
                <span>
                  Claimant opens link → sets password → account + claimant
                  pre-created.
                </span>
              </li>
              <li className="flex gap-3">
                <span className="w-6 h-6 bg-[#0033A0] text-white text-xs font-bold inline-flex items-center justify-center">
                  4
                </span>
                <span>Weekly reminders begin automatically.</span>
              </li>
            </ol>
          </div>
        </div>
      </section>

      <footer className="border-t border-border bg-muted">
        <div className="max-w-[1440px] mx-auto px-6 py-6 flex items-center justify-between flex-wrap gap-3">
          <div className="text-xs text-muted-foreground">
            Unofficial tool — not affiliated with the Illinois Department of
            Employment Security. Mirrors ADJ034F form structure for personal
            record-keeping.
          </div>
          <div className="flex gap-4 text-xs">
            <Link
              to="/login"
              className="text-[#0033A0] dark:text-[#5a86ff] font-semibold underline"
            >
              Sign in
            </Link>
            <Link to="/forgot-password" className="text-muted-foreground underline">
              Forgot password
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}