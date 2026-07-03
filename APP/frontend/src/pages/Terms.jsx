import { Link } from "react-router-dom";
import { ScalesIcon } from "@phosphor-icons/react";

const Section = ({ title, children }) => (
  <div className="mb-10">
    <h2 className="font-display font-black text-xl tracking-tight mb-4 pb-2 border-b border-border">
      {title}
    </h2>
    <div className="text-sm text-foreground leading-relaxed space-y-3">
      {children}
    </div>
  </div>
);

export default function Terms() {
  const updated = "June 6, 2026";

  return (
    <div className="min-h-screen bg-background">
      <div className="h-1 bg-[#0033A0]" />

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
        <div className="flex items-center gap-4 mb-10">
          <div className="w-14 h-14 bg-[#0033A0] flex items-center justify-center flex-shrink-0">
            <ScalesIcon size={28} weight="bold" className="text-white" />
          </div>
          <div>
            <p className="text-xs font-bold tracking-widest text-muted-foreground uppercase mb-1">
              Legal
            </p>
            <h1 className="font-display font-black text-3xl tracking-tight leading-none">
              Terms & Conditions
            </h1>
            <p className="text-xs text-muted-foreground mt-2">
              Last updated: {updated}
            </p>
          </div>
        </div>

        <Section title="Acceptance of Terms">
          <p>
            By accessing or using Illinois UI Job Search Tracker ("the App"),
            you agree to be bound by these Terms and Conditions. If you do not
            agree to these terms, do not use the App.
          </p>
        </Section>

        <Section title="Description of Service">
          <p>
            Illinois UI Job Search Tracker is a web-based compliance tool
            designed to help Illinois unemployment insurance claimants track and
            document their weekly work-search activities as required by the
            Illinois Department of Employment Security (IDES).
          </p>
          <p>
            The App helps users maintain records of work-search contacts,
            generate IDES ADJ034F Work Search Record forms, receive compliance
            reminders via email and SMS, and manage claimant profiles.
          </p>
        </Section>

        <Section title="Important Disclaimer — Not Official IDES Software">
          <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 p-4">
            <p className="font-semibold text-amber-900 dark:text-amber-200">
              Illinois UI Job Search Tracker is an independent, privately
              developed tool. It is NOT affiliated with, endorsed by, or
              operated by the Illinois Department of Employment Security (IDES)
              or the State of Illinois.
            </p>
            <p className="mt-2 text-amber-800 dark:text-amber-300">
              Use of this App does not guarantee compliance with IDES
              requirements. You are solely responsible for ensuring your
              work-search records meet all applicable IDES standards. Always
              verify your compliance status directly with IDES.
            </p>
          </div>
        </Section>

        <Section title="User Responsibilities">
          <p>
            <strong>Accuracy of records:</strong> You are responsible for
            ensuring that all work-search records you enter are accurate and
            truthful. Submitting false work-search records to IDES is a
            violation of Illinois law and may result in overpayment, penalties,
            or prosecution.
          </p>
          <p>
            <strong>Record retention:</strong> Per IDES requirements, you must
            keep your written work-search records for any benefit week until 53
            weeks have passed from the end of that week, or until any pending
            appeals are fully resolved.
          </p>
          <p>
            <strong>Account security:</strong> You are responsible for
            maintaining the confidentiality of your account credentials and for
            all activity that occurs under your account.
          </p>
          <p>
            <strong>Accurate contact information:</strong> You are responsible
            for providing accurate email addresses and phone numbers for
            reminders and notifications.
          </p>
        </Section>

        <Section title="SMS Terms">
          <p>
            By opting in to SMS reminders through the App or via the SMS opt-in
            page, you consent to receive automated text messages from Illinois
            UI Job Search Tracker via Twilio.
          </p>
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li>Message frequency: typically 1–3 messages per benefit week</li>
            <li>Message and data rates may apply</li>
            <li>
              Reply <strong>STOP</strong> to unsubscribe at any time
            </li>
            <li>
              Reply <strong>HELP</strong> for assistance
            </li>
            <li>
              Opt-out is effective immediately upon receipt of your STOP reply
            </li>
          </ul>
          <p>
            You can also disable SMS reminders at any time from your Claimant
            profile inside the App.
          </p>
        </Section>

        <Section title="Acceptable Use">
          <p>You agree not to:</p>
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li>
              Use the App to submit false or fraudulent work-search records
            </li>
            <li>
              Attempt to gain unauthorized access to other users' accounts or
              data
            </li>
            <li>
              Reverse engineer, decompile, or attempt to extract the App's
              source code
            </li>
            <li>
              Use the App in any way that violates applicable federal, state, or
              local laws
            </li>
            <li>
              Resell or commercially exploit the App without written permission
            </li>
          </ul>
        </Section>

        <Section title="Intellectual Property">
          <p>
            All content, features, and functionality of the App — including but
            not limited to the design, code, logos, and text — are owned by
            KMG123 Enterprises LLC and are protected by applicable intellectual
            property laws.
          </p>
          <p>
            The ADJ034F Work Search Record form is a public document produced by
            the Illinois Department of Employment Security and is used in
            accordance with its public availability for compliance purposes.
          </p>
        </Section>

        <Section title="Limitation of Liability">
          <p>
            To the fullest extent permitted by law, Illinois UI Job Search
            Tracker and KMG123 Enterprises LLC shall not be liable for any
            indirect, incidental, special, or consequential damages arising from
            your use of the App, including but not limited to loss of benefits,
            penalties from IDES, or data loss.
          </p>
          <p>
            The App is provided "as is" without warranties of any kind, express
            or implied. We do not warrant that the App will be uninterrupted,
            error-free, or that defects will be corrected.
          </p>
        </Section>

        <Section title="Termination">
          <p>
            We reserve the right to suspend or terminate your account at any
            time for violation of these Terms. You may delete your account at
            any time from within the App. Upon termination, your data will be
            permanently removed within 30 days.
          </p>
        </Section>

        <Section title="Changes to These Terms">
          <p>
            We may update these Terms from time to time. When we do, we will
            update the "Last updated" date at the top of this page. Continued
            use of the App after changes constitutes acceptance of the updated
            Terms.
          </p>
        </Section>

        <Section title="Governing Law">
          <p>
            These Terms are governed by the laws of the State of Illinois,
            without regard to its conflict of law provisions. Any disputes
            arising from these Terms shall be resolved in the courts of
            Illinois.
          </p>
        </Section>

        <Section title="Contact">
          <p>For questions about these Terms, contact us at:</p>
          <p className="font-mono text-xs bg-muted border border-border p-3">
            Illinois UI Job Search Tracker
            <br />
            illinoisjobtracker.app
            <br />
            KMG123 Enterprises LLC
          </p>
        </Section>
      </main>

      <footer className="border-t border-border mt-8">
        <div className="max-w-4xl mx-auto px-6 py-6 flex items-center justify-between text-xs text-muted-foreground">
          <span>
            © {new Date().getFullYear()} Illinois UI Job Search Tracker
          </span>
          <div className="flex gap-4">
            <Link to="/sms-opt-in" className="hover:text-foreground">
              SMS Opt-In
            </Link>
            <Link to="/privacy" className="hover:text-foreground">
              Privacy Policy
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}