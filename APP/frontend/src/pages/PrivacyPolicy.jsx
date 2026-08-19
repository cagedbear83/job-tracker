const items = [
  ["information", "1. What Information Do We Collect?", "We collect information you provide when you create an account, use the Services, contact us, or make a purchase. This may include names, email addresses, phone numbers, mailing and billing addresses, usernames, job titles, contact preferences, authentication information, and payment-related information."],
  ["processing", "2. How Do We Process Your Information?", "We process information to create and manage accounts, deliver and improve the Services, respond to support requests, communicate with you, prevent fraud, protect the Services, and comply with law."],
  ["sharing", "3. When and With Whom Do We Share Your Personal Information?", "We may share information with service providers that help operate the Services, including Google Cloud AI, ClickSend, DigitalOcean, Heroku, Stripe, PayPal, Sentry, and Datadog. We may also share information in connection with business transfers or with affiliates that must honor this Privacy Notice."],
  ["ai", "4. Do We Offer Artificial Intelligence-Based Products?", "We may offer products, features, or tools powered by artificial intelligence, machine learning, or similar technologies. Our AI services may use third-party providers, including Google Cloud AI, and are governed by this Privacy Notice."],
  ["retention", "5. How Long Do We Keep Your Information?", "We retain personal information only as long as necessary for the purposes described in this Privacy Notice, unless a longer period is required by law. The policy states that no purpose requires retention longer than thirteen months after the beginning of an account's idle period."],
  ["security", "6. How Do We Keep Your Information Safe?", "We use reasonable organizational and technical safeguards. However, no online transmission or storage system is completely secure, and you should access the Services only in a secure environment."],
  ["minors", "7. Do We Collect Information From Minors?", "We do not knowingly collect data from, market to, or sell personal information of children under 18 years of age."],
  ["rights", "8. What Are Your Privacy Rights?", "Depending on where you live, you may have rights to access, correct, copy, delete, or withdraw consent regarding your personal information. You may also review, change, or terminate account information through your account settings or by contacting us."],
  ["dnt", "9. Controls for Do-Not-Track Features", "Because no uniform standard for recognizing Do-Not-Track signals has been finalized, we do not currently respond to browser Do-Not-Track signals."],
  ["us-rights", "10. Do United States Residents Have Specific Privacy Rights?", "Residents of certain US states may have rights to know whether we process personal data, access it, correct inaccuracies, request deletion, obtain a copy, and avoid discrimination for exercising privacy rights. We honor Global Privacy Control signals where required."],
  ["updates", "11. Do We Make Updates to This Notice?", "We may update this notice when necessary. The revised date will appear at the top of the policy, and we may provide notice of material changes."],
  ["contact", "12. How Can You Contact Us About This Notice?", "For questions or comments about this Privacy Notice, email privacy@illinoisjobtracker.com."],
  ["requests", "13. How Can You Review, Update, or Delete Your Data?", "To request access, correction, deletion, or information about your personal data, visit www.illinoisjobtracker.com/contact or contact us by email."],
];

export default function PrivacyPolicy() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="brand-bar" />
      <article className="mx-auto w-full max-w-4xl px-4 py-10 sm:px-6 lg:py-16">
        <header className="border-b border-border pb-8">
          <p className="kbd-label mb-3">Illinois UI Job Search Tracker</p>
          <h1 className="font-display text-4xl font-bold tracking-tight sm:text-5xl">Privacy Policy</h1>
          <p className="mt-3 text-sm text-muted-foreground"><strong>Last updated:</strong> August 18, 2026</p>
        </header>

        <section className="mt-8 border-l-4 border-primary bg-secondary p-5">
          <p>This Privacy Notice for <strong>KMG123 Enterprises LLC</strong>, doing business as <strong>Illinois UI Job Search Tracker</strong>, explains how we access, collect, store, use, and share personal information when you use our website, mobile application, and related Services.</p>
          <p className="mt-4">Questions or concerns? Email <a className="font-medium text-primary underline underline-offset-4" href="mailto:privacy@illinoisjobtracker.com">privacy@illinoisjobtracker.com</a>.</p>
        </section>

        <nav className="mt-8 border border-border bg-card p-5" aria-label="Table of contents">
          <p className="kbd-label mb-3">Table of contents</p>
          <ol className="grid gap-2 text-sm sm:grid-cols-2">
            {items.map(([id, title]) => <li key={id}><a className="text-primary underline underline-offset-4" href={`#${id}`}>{title}</a></li>)}
          </ol>
        </nav>

        <section id="information" className="mt-12 scroll-mt-6">
          <h2 className="font-display text-2xl font-bold">1. What Information Do We Collect?</h2>
          <h3 className="mt-6 text-lg font-semibold">Personal Information You Disclose to Us</h3>
          <p className="mt-3"><strong>In short:</strong> We collect personal information that you provide to us.</p>
          <ul className="mt-4 list-disc space-y-1 pl-6"><li>Names, phone numbers, and email addresses</li><li>Mailing and billing addresses</li><li>Job titles, usernames, passwords, and contact preferences</li><li>Contact or authentication data</li><li>Debit or credit card numbers and related payment data</li></ul>
          <h3 className="mt-6 text-lg font-semibold">Payment and Sensitive Information</h3>
          <p className="mt-3">Where necessary, with consent, or as permitted by law, we may process financial data. Payment data is handled and stored by Stripe. Review <a className="text-primary underline underline-offset-4" href="https://stripe.com/privacy">Stripe&apos;s privacy policy</a>.</p>
        </section>

        {items.slice(1).map(([id, title, content]) => (
          <section id={id} className="mt-12 scroll-mt-6" key={id}>
            <h2 className="font-display text-2xl font-bold">{title}</h2>
            <p className="mt-3 leading-7">{content}</p>
            {id === "contact" && <p className="mt-3">Email <a className="font-medium text-primary underline underline-offset-4" href="mailto:privacy@illinoisjobtracker.com">privacy@illinoisjobtracker.com</a>.</p>}
            {id === "requests" && <p className="mt-3">Submit a request through <a className="font-medium text-primary underline underline-offset-4" href="https://www.illinoisjobtracker.com/contact">www.illinoisjobtracker.com/contact</a>.</p>}
          </section>
        ))}
      </article>
    </main>
  );
}
