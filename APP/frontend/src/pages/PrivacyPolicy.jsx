// APP/frontend/src/pages/PrivacyPolicy.jsx
// Drop-in replacement. Uses the app's existing semantic Tailwind tokens.
// ⚠️ ATTORNEY REVIEW REQUIRED before taking live payments or publishing publicly.

import { useEffect } from "react";

const EFFECTIVE_DATE = "July 14, 2026";
const COMPANY = "KMG123 Enterprises LLC";
const APP_NAME = "Illinois UI Job Search Tracker";
const APP_URL = "https://illinoisjobtracker.app";
const SUPPORT_EMAIL = "support@illinoisjobtracker.app";

function Section({ title, children }) {
  return (
    <section className="mb-8">
      <h2 className="text-lg font-semibold text-foreground mb-3">{title}</h2>
      <div className="space-y-3 text-sm text-muted-foreground leading-relaxed">
        {children}
      </div>
    </section>
  );
}

function SubSection({ title, children }) {
  return (
    <div className="mt-4">
      <h3 className="text-sm font-semibold text-foreground mb-2">{title}</h3>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

export default function PrivacyPolicy() {
  useEffect(() => {
    document.title = `Privacy Policy — ${APP_NAME}`;
  }, []);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        {/* Header */}
        <div className="mb-10">
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-2">
            Legal
          </p>
          <h1 className="text-3xl font-bold text-foreground mb-3">Privacy Policy</h1>
          <p className="text-sm text-muted-foreground">
            Effective date: {EFFECTIVE_DATE}
          </p>
          <p className="mt-3 text-sm text-muted-foreground">
            This Privacy Policy describes how {COMPANY} ("{APP_NAME}", "we", "us",
            or "our") collects, uses, and protects the personal information of users
            of {APP_URL}. By creating an account or using the Service, you agree to
            this policy.
          </p>
          <div className="mt-4 rounded-md border border-amber-400/40 bg-amber-400/10 px-4 py-3">
            <p className="text-xs text-[#EAB308] dark:text-amber-300 font-medium">
              {APP_NAME} is a private tool developed by {COMPANY}. It is{" "}
              <strong>not affiliated with, endorsed by, or connected to</strong> the
              Illinois Department of Employment Security (IDES) or the State of
              Illinois in any way.
            </p>
          </div>
        </div>

        {/* 1. Information We Collect */}
        <Section title="1. Information We Collect">
          <SubSection title="Account Information">
            <p>
              When you register, we collect your first name, last name, email
              address, and a hashed version of your password (we never store your
              password in plain text). We do not collect your Social Security
              number, IDES PIN, or any government-issued credentials.
            </p>
          </SubSection>

          <SubSection title="Claimant & Work-Search Records">
            <p>
              To provide the core service, we store the job contact records you
              enter: employer name, contact date, contact method, job title,
              contact name, phone/email, and result/notes. We also store the
              benefit week periods you create and any status you record (e.g.,
              certification day, week ending date).
            </p>
          </SubSection>

          <SubSection title="AI Screenshot Import (Pro & Case Worker)">
            <p>
              If you use the AI import feature, you upload a screenshot of a job
              listing or confirmation email. That image is transmitted to Google's
              Gemini API for text extraction and then{" "}
              <strong>immediately discarded</strong>. We do not store uploaded
              images. The extracted text fields are returned to you for review
              before being saved.
            </p>
          </SubSection>

          <SubSection title="Phone Number (Optional)">
            <p>
              If you opt in to SMS reminders, we collect your phone number and
              store it on your claimant profile. You verify it via a one-time
              passcode (OTP) before any messages are sent. You may opt out at any
              time by replying STOP to any message or removing your number from
              your profile.
            </p>
          </SubSection>

          <SubSection title="Payment Information">
            <p>
              Billing is handled entirely by Stripe. We never see, store, or
              process your credit card number, CVV, or full card details. We store
              your Stripe Customer ID and subscription status so we can manage
              your account tier. See Section 4 for more on Stripe.
            </p>
          </SubSection>

          <SubSection title="Case Worker Accounts">
            <p>
              Case Worker subscribers may add claimant profiles on behalf of the
              individuals they serve. Those claimants' job contact data is stored
              in association with the Case Worker's account. Each claimant must
              sign a Claimant Liability Release before a Case Worker account can
              log contacts on their behalf. Case Workers are responsible for
              obtaining and retaining those releases.
            </p>
          </SubSection>

          <SubSection title="Usage & Log Data">
            <p>
              We collect standard server logs including your IP address, browser
              type, and pages visited. We log authentication events (successful
              logins, failed login attempts, lockouts, password resets) for
              security monitoring. We do not log the contents of your job contact
              records in server logs.
            </p>
          </SubSection>
        </Section>

        {/* 2. How We Use Your Information */}
        <Section title="2. How We Use Your Information">
          <p>We use the information we collect to:</p>
          <ul className="list-disc list-inside space-y-1 pl-2 mt-2">
            <li>Create and manage your account</li>
            <li>
              Store, display, and export your job search contact records and
              benefit week history
            </li>
            <li>
              Generate the ADJ034F work-search record (PDF) and CSV exports on
              demand — these files are generated ephemerally and{" "}
              <strong>never stored on our servers</strong>
            </li>
            <li>Send transactional emails (email verification, password reset)</li>
            <li>
              Send SMS reminders about your certification deadlines (only if you
              opted in)
            </li>
            <li>Enforce your subscription tier and billing status</li>
            <li>Monitor for security incidents and unauthorized access</li>
            <li>
              Comply with the Illinois Personal Information Protection Act (PIPA)
              and applicable law
            </li>
          </ul>
          <p className="mt-3">
            We do not sell your personal information. We do not use your job
            contact data for advertising.
          </p>
        </Section>

        {/* 3. Data Retention */}
        <Section title="3. Data Retention">
          <p>
            We retain your account and job contact records for as long as your
            account is active, plus a period needed to comply with our legal
            obligations.
          </p>
          <SubSection title="53-Week IDES Retention Policy">
            <p>
              Benefit week records and job contact data are subject to a 53-week
              maximum retention window, consistent with the IDES audit period.
              Records approaching this limit trigger automated notices at 14 days,
              7 days, and 24 hours before expiration. Each notice contains a
              direct link to generate and download your ADJ034F for that week
              before it is removed.
            </p>
          </SubSection>
          <SubSection title="Account Deletion">
            <p>
              You may request deletion of your account by contacting us at{" "}
              <a
                href={`mailto:${SUPPORT_EMAIL}`}
                className="text-primary underline underline-offset-2"
              >
                {SUPPORT_EMAIL}
              </a>
              . Upon deletion, your account and all associated personal
              information are removed from our systems within 30 days, except
              where retention is required by law or for fraud prevention.
            </p>
          </SubSection>
          <SubSection title="Downgrade Policy">
            <p>
              If you downgrade to a lower tier, your historical records are
              archived and access is locked until you re-upgrade. Records are
              never deleted on downgrade. The 53-week retention clock continues
              to run on archived data.
            </p>
          </SubSection>
        </Section>

        {/* 4. Third-Party Services */}
        <Section title="4. Third-Party Service Providers">
          <p>
            We share limited personal information with the following vendors
            solely to operate the Service. Each is contractually required to
            protect your data:
          </p>

          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 pr-4 font-semibold text-foreground">
                    Vendor
                  </th>
                  <th className="text-left py-2 pr-4 font-semibold text-foreground">
                    Purpose
                  </th>
                  <th className="text-left py-2 font-semibold text-foreground">
                    Data shared
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {[
                  {
                    vendor: "MongoDB Atlas",
                    purpose: "Database (data storage)",
                    data: "All account and record data",
                  },
                  {
                    vendor: "DigitalOcean",
                    purpose: "Backend hosting",
                    data: "All data passing through the API",
                  },
                  {
                    vendor: "Vercel",
                    purpose: "Frontend hosting",
                    data: "IP address, browser metadata",
                  },
                  {
                    vendor: "Mailgun",
                    purpose: "Transactional email",
                    data: "Email address, email content",
                  },
                  {
                    vendor: "Twilio",
                    purpose: "SMS reminders (opt-in only)",
                    data: "Phone number, reminder message",
                  },
                  {
                    vendor: "Google (Gemini API)",
                    purpose: "AI screenshot import (Pro/CW)",
                    data: "Uploaded image (discarded after extraction)",
                  },
                  {
                    vendor: "Stripe",
                    purpose: "Payment processing",
                    data: "Email address, subscription status; card details go directly to Stripe",
                  },
                ].map(({ vendor, purpose, data }) => (
                  <tr key={vendor}>
                    <td className="py-2 pr-4 font-medium text-foreground">
                      {vendor}
                    </td>
                    <td className="py-2 pr-4">{purpose}</td>
                    <td className="py-2">{data}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="mt-3">
            We do not sell, rent, or trade your personal information to any other
            third party.
          </p>
        </Section>

        {/* 5. Security */}
        <Section title="5. Security">
          <p>
            We implement industry-standard security controls including:
          </p>
          <ul className="list-disc list-inside space-y-1 pl-2 mt-2">
            <li>Passwords stored as bcrypt hashes (never in plain text)</li>
            <li>All data encrypted in transit via TLS/HTTPS</li>
            <li>All data encrypted at rest in MongoDB Atlas</li>
            <li>
              Account lockout after repeated failed login attempts, with
              configurable thresholds
            </li>
            <li>
              Single active session enforcement — logging in on a new device
              invalidates prior sessions
            </li>
            <li>
              NIST SP 800-63B-aligned password requirements (minimum 12
              characters, entropy-based strength meter, compromised-password
              screening)
            </li>
            <li>
              Platform admin access requires step-up re-authentication and is
              logged in an append-only audit trail
            </li>
          </ul>
          <p className="mt-3">
            No method of transmission or storage is 100% secure. In the event of
            a data breach affecting your personal information, we will notify you
            as required by the Illinois Personal Information Protection Act (PIPA,
            815 ILCS 530) — without unreasonable delay, and to the Illinois
            Attorney General's office if 500 or more residents are affected.
          </p>
        </Section>

        {/* 6. SMS */}
        <Section title="6. SMS Communications">
          <p>
            If you opt in to SMS reminders, the following terms apply:
          </p>
          <ul className="list-disc list-inside space-y-1 pl-2 mt-2">
            <li>
              Message frequency is approximately 1–3 messages per week per active
              claimant, depending on your certification schedule.
            </li>
            <li>Message and data rates may apply.</li>
            <li>
              You may opt out at any time by replying <strong>STOP</strong> to any
              message. You may re-opt-in by replying <strong>START</strong>.
            </li>
            <li>
              Reply <strong>HELP</strong> for assistance. You may also contact us
              at {SUPPORT_EMAIL}.
            </li>
            <li>
              SMS messages are sent via Twilio. Your phone number is not shared
              with any other party.
            </li>
          </ul>
        </Section>

        {/* 7. Your Rights */}
        <Section title="7. Your Rights">
          <p>
            Under the Illinois Personal Information Protection Act and applicable
            law, you have the right to:
          </p>
          <ul className="list-disc list-inside space-y-1 pl-2 mt-2">
            <li>
              <strong>Access</strong> — request a copy of the personal information
              we hold about you
            </li>
            <li>
              <strong>Correction</strong> — request correction of inaccurate
              information
            </li>
            <li>
              <strong>Deletion</strong> — request deletion of your account and
              associated personal data
            </li>
            <li>
              <strong>Opt-out of SMS</strong> — reply STOP to any SMS at any time
            </li>
          </ul>
          <p className="mt-3">
            To exercise any of these rights, contact us at{" "}
            <a
              href={`mailto:${SUPPORT_EMAIL}`}
              className="text-primary underline underline-offset-2"
            >
              {SUPPORT_EMAIL}
            </a>
            . We will respond within 30 days.
          </p>
        </Section>

        {/* 8. Children */}
        <Section title="8. Children">
          <p>
            The Service is intended for adults 18 years of age and older. We do
            not knowingly collect personal information from anyone under 18. If
            you believe we have collected information from a minor, contact us at{" "}
            <a
              href={`mailto:${SUPPORT_EMAIL}`}
              className="text-primary underline underline-offset-2"
            >
              {SUPPORT_EMAIL}
            </a>{" "}
            and we will delete it promptly.
          </p>
        </Section>

        {/* 9. Changes */}
        <Section title="9. Changes to This Policy">
          <p>
            We may update this Privacy Policy from time to time. When we do, we
            will revise the effective date at the top of this page and, for
            material changes, notify you by email or by a notice in the
            application. Your continued use of the Service after any update
            constitutes your acceptance of the revised policy.
          </p>
        </Section>

        {/* 10. Contact */}
        <Section title="10. Contact">
          <p>
            Questions about this Privacy Policy or your data? Contact us:
          </p>
          <div className="mt-2 rounded-md border border-border bg-muted/40 px-4 py-3 text-sm">
            <p className="font-medium text-foreground">{COMPANY}</p>
            <p>
              <a
                href={`mailto:${SUPPORT_EMAIL}`}
                className="text-primary underline underline-offset-2"
              >
                {SUPPORT_EMAIL}
              </a>
            </p>
            <p>{APP_URL}</p>
          </div>
        </Section>
      </div>
    </div>
  );
}