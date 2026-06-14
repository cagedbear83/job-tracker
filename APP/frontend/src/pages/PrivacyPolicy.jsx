import { Link } from "react-router-dom";
import { ShieldCheckIcon } from "@phosphor-icons/react";

const Section = ({ title, children }) => (
  <div className="mb-10">
    <h2 className="font-display font-black text-xl tracking-tight mb-4 pb-2 border-b border-zinc-200">
      {title}
    </h2>
    <div className="text-sm text-zinc-700 leading-relaxed space-y-3">
      {children}
    </div>
  </div>
);

export default function PrivacyPolicy() {
  const updated = "June 6, 2026";

  return (
    <div className="min-h-screen bg-white">
      <div className="h-1 bg-[#0033A0]" />

      <header className="border-b border-zinc-200 bg-white">
        <div className="max-w-4xl mx-auto px-6 py-3 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-9 h-9 bg-[#0033A0] flex items-center justify-center text-white font-display font-black tracking-tight text-sm">
              IL
            </div>
            <div>
              <div className="font-display font-black text-base leading-none tracking-tight">
                Illinois UI Tracker
              </div>
              <div className="text-[10px] font-bold tracking-widest text-zinc-500 uppercase mt-1">
                Work Search Compliance
              </div>
            </div>
          </Link>
          <Link
            to="/login"
            className="text-sm font-semibold text-[#0033A0] hover:underline"
          >
            Sign In
          </Link>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-6 py-16">
        <div className="flex items-center gap-4 mb-10">
          <div className="w-14 h-14 bg-[#0033A0] flex items-center justify-center flex-shrink-0">
            <ShieldCheckIcon size={28} weight="bold" className="text-white" />
          </div>
          <div>
            <p className="text-xs font-bold tracking-widest text-zinc-500 uppercase mb-1">
              Legal
            </p>
            <h1 className="font-display font-black text-3xl tracking-tight leading-none">
              Privacy Policy
            </h1>
            <p className="text-xs text-zinc-500 mt-2">
              Last updated: {updated}
            </p>
          </div>
        </div>

        <Section title="Overview">
          <p>
            Illinois UI Job Search Tracker ("the App", "we", "us") is a
            compliance tool that helps Illinois unemployment insurance claimants
            track their required work-search contacts as mandated by the
            Illinois Department of Employment Security (IDES). This Privacy
            Policy explains what information we collect, how we use it, and your
            rights regarding your data.
          </p>
        </Section>

        <Section title="Information We Collect">
          <p>
            <strong>Account information:</strong> Name, email address, and
            password (stored as a secure hash) when you create an account.
          </p>
          <p>
            <strong>Claimant profile data:</strong> Illinois IDES claimant ID,
            Social Security Number (last 4 digits only), address, and job title
            as entered by you for compliance tracking purposes.
          </p>
          <p>
            <strong>Work-search records:</strong> Employer names, addresses,
            contact dates, contact methods, types of work sought, and results of
            job contacts you log in the app.
          </p>
          <p>
            <strong>Phone number:</strong> If you opt in to SMS reminders, we
            collect your mobile phone number in E.164 format.
          </p>
          <p>
            <strong>Usage data:</strong> An audit log of actions taken within
            the app (logins, record creation, exports) for compliance and
            security purposes.
          </p>
        </Section>

        <Section title="How We Use Your Information">
          <p>
            <strong>To provide the service:</strong> Your work-search data is
            used solely to generate compliance records, weekly summaries, and
            IDES ADJ034F form exports.
          </p>
          <p>
            <strong>Email reminders:</strong> If enabled, we use your email
            address to send weekly work-search compliance reminders via Mailgun.
          </p>
          <p>
            <strong>SMS reminders:</strong> If you opt in, we use your phone
            number to send automated SMS reminders via Twilio. Message frequency
            is typically 1–3 messages per benefit week. Standard message and
            data rates may apply. Reply STOP to unsubscribe at any time.
          </p>
          <p>
            <strong>We do not sell your data.</strong> Your information is never
            sold, rented, or shared with third parties for marketing purposes.
          </p>
        </Section>

        <Section title="Data Storage and Security">
          <p>
            Your data is stored in a secured MongoDB Atlas cloud database hosted
            in the United States. We use industry-standard encryption for data
            in transit (HTTPS/TLS) and at rest.
          </p>
          <p>
            Passwords are hashed using bcrypt and are never stored in plain
            text. JWT tokens are used for session authentication with a secure
            secret key.
          </p>
          <p>
            You should not discard your work-search records for any benefit week
            until 53 weeks have passed from the end of that week, per IDES
            requirements. The App is designed to help you maintain these
            records.
          </p>
        </Section>

        <Section title="Third-Party Services">
          <p>We use the following third-party services to operate the App:</p>
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li>
              <strong>MongoDB Atlas</strong> — cloud database storage
            </li>
            <li>
              <strong>Mailgun</strong> — transactional email delivery
            </li>
            <li>
              <strong>Twilio</strong> — SMS message delivery
            </li>
            <li>
              <strong>Google Gemini API</strong> — AI-powered screenshot import
              (optional feature)
            </li>
            <li>
              <strong>DigitalOcean</strong> — backend hosting
            </li>
            <li>
              <strong>Vercel</strong> — frontend hosting
            </li>
          </ul>
          <p>
            Each service operates under its own privacy policy and data
            processing terms.
          </p>
        </Section>

        <Section title="SMS Terms">
          <p>
            By opting in to SMS reminders you agree to receive automated text
            messages from Illinois UI Job Search Tracker. Message frequency
            varies, typically 1–3 messages per benefit week. Message and data
            rates may apply.
          </p>
          <p>
            <strong>To opt out:</strong> Reply STOP to any message at any time.
            You will receive a confirmation and no further messages will be
            sent.
          </p>
          <p>
            <strong>For help:</strong> Reply HELP or visit
            illinoisjobtracker.app
          </p>
          <p>
            You can also disable SMS reminders at any time from your Claimant
            profile inside the App.
          </p>
        </Section>

        <Section title="Your Rights">
          <p>
            You may request to view, correct, or delete your personal data at
            any time by logging into your account or contacting us. Account
            deletion removes all associated claimant profiles, work-search
            records, and personal data from our systems.
          </p>
        </Section>

        <Section title="Data Retention">
          <p>
            We retain your data for as long as your account is active. Audit
            logs are retained for 12 months. If you delete your account, all
            personal data is permanently removed within 30 days.
          </p>
        </Section>

        <Section title="Contact">
          <p>For privacy-related questions or data requests, contact us at:</p>
          <p className="font-mono text-xs bg-zinc-50 border border-zinc-200 p-3">
            Illinois UI Job Search Tracker
            <br />
            illinoisjobtracker.app
            <br />
            KMG123 Enterprises LLC
          </p>
        </Section>
      </main>

      <footer className="border-t border-zinc-200 mt-8">
        <div className="max-w-4xl mx-auto px-6 py-6 flex items-center justify-between text-xs text-zinc-500">
          <span>
            © {new Date().getFullYear()} Illinois UI Job Search Tracker
          </span>
          <div className="flex gap-4">
            <Link to="/sms-opt-in" className="hover:text-zinc-900">
              SMS Opt-In
            </Link>
            <Link to="/terms" className="hover:text-zinc-900">
              Terms & Conditions
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
