const sections = [
  ["services", "1. Our Services", "The Services are not intended for distribution to or use by a person or entity where use would violate law or regulation or subject us to a registration requirement. The Services are not designed for uses subject to industry-specific requirements such as HIPAA, FISMA, or GLBA."],
  ["ip", "2. Intellectual Property Rights", "We own or license intellectual property rights in the Services, including source code, designs, text, graphics, software, trademarks, and logos. Subject to these Terms, you receive a limited, non-exclusive, non-transferable, revocable license for personal, non-commercial use or internal business purposes."],
  ["representations", "3. User Representations", "You represent that submitted information is accurate and current, you have legal capacity, you are at least 18 years old, you will not access the Services using bots or scripts, and you will comply with applicable law."],
  ["registration", "4. User Registration", "You may be required to register. You are responsible for keeping your password confidential and for all activity under your account."],
  ["payment", "5. Purchases and Payment", "We accept Visa, Mastercard, American Express, Discover, and PayPal. You agree to provide current, complete, and accurate account and payment information. Prices may change, tax may apply, and payments are in US dollars."],
  ["subscriptions", "6. Subscriptions", "Subscriptions renew automatically unless canceled. New users receive a 14-day free trial. All purchases are non-refundable. You may cancel through your account, and cancellation takes effect at the end of the current paid term."],
  ["prohibited", "7. Prohibited Activities", "You may not use the Services for unauthorized purposes; use bots, scripts, or automated data collection; interfere with security; obtain account information improperly; upload harmful material; or violate applicable law."],
  ["contributions", "8. User Generated Contributions", "If the Services allow contributions, you are responsible for them and represent that they are lawful, accurate, non-infringing, and that you have all rights needed to submit them."],
  ["license", "9. Contribution License", "By posting Contributions, you grant us a worldwide, royalty-free, perpetual, irrevocable, transferable, sublicensable right to use, reproduce, distribute, publish, display, translate, adapt, and otherwise exploit them for lawful purposes."],
  ["third-party", "10. Third-Party Websites and Content", "The Services may link to third-party websites or content. Your use of those services is at your own risk and subject to their own terms and privacy policies."],
  ["management", "11. Services Management", "We may monitor the Services for violations, restrict access, remove Contributions, and take other steps to protect our rights and support proper operation."],
  ["privacy", "12. Privacy Policy", "By using the Services, you agree to our Privacy Policy, which is incorporated into these Terms."],
  ["term", "13. Term and Termination", "These Terms remain effective while you use the Services. We may deny access, terminate accounts, remove content, or end use of the Services for a breach of these Terms."],
  ["changes", "14. Modifications and Interruptions", "We may change, modify, remove, or discontinue any part of the Services at any time. We do not guarantee uninterrupted availability."],
  ["law", "15. Governing Law", "These Terms and your use of the Services are governed by the laws of the State of Illinois, without regard to conflict-of-law principles."],
  ["disputes", "16. Dispute Resolution", "To the extent permitted by law, disputes arising from these Terms or the Services will be resolved in Illinois courts."],
  ["corrections", "17. Corrections", "Information on the Services may contain errors, inaccuracies, or omissions. We may correct or update information at any time without notice."],
  ["disclaimer", "18. Disclaimer", "The Services are provided on an as-is and as-available basis. To the fullest extent permitted by law, we disclaim all express and implied warranties."],
  ["liability", "19. Limitations of Liability", "To the fullest extent permitted by law, we are not liable for indirect, consequential, incidental, special, or punitive damages arising from use of the Services."],
  ["indemnity", "20. Indemnification", "You agree to defend, indemnify, and hold us harmless from claims, losses, liabilities, damages, and expenses arising from your use of the Services, Contributions, breach of these Terms, or violation of another party's rights."],
  ["data", "21. User Data", "We maintain certain data you transmit to the Services for managing performance. You are responsible for your data, and we are not liable for data loss or corruption."],
  ["electronic", "22. Electronic Communications, Transactions, and Signatures", "You consent to electronic communications and agree that electronic agreements, notices, disclosures, and records satisfy requirements for written communications."],
  ["sms", "23. SMS Text Messaging", "If you opt in to SMS messages, you consent to receive service-related text messages. Message and data rates may apply, and you may opt out at any time."],
  ["california", "24. California Users and Residents", "California residents may contact the California Department of Consumer Affairs if a complaint with us is not resolved satisfactorily."],
  ["misc", "25. Miscellaneous", "These Terms and posted policies constitute the entire agreement concerning the Services. If a provision is unenforceable, it will be severed and the remaining provisions will remain in effect."],
];

export default function TermsOfService() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="brand-bar" />
      <article className="mx-auto w-full max-w-4xl px-4 py-10 sm:px-6 lg:py-16">
        <header className="border-b border-border pb-8">
          <p className="kbd-label mb-3">Illinois UI Job Search Tracker</p>
          <h1 className="font-display text-4xl font-bold tracking-tight sm:text-5xl">Terms of Service</h1>
          <p className="mt-3 text-sm text-muted-foreground"><strong>Last updated:</strong> August 18, 2026</p>
        </header>

        <section className="mt-8 border-l-4 border-primary bg-secondary p-5">
          <h2 className="font-display text-xl font-bold">Agreement to Our Legal Terms</h2>
          <p className="mt-3">These Terms are a legally binding agreement between you and <strong>KMG123 Enterprises LLC</strong>, doing business as <strong>Illinois UI Job Search Tracker</strong>.</p>
          <p className="mt-3">4860 N Paulina St, Chicago, IL 60640 · <a className="font-medium text-primary underline underline-offset-4" href="tel:+18003125555">1-800-312-5555</a> · <a className="font-medium text-primary underline underline-offset-4" href="mailto:contact@illinoisjobtracker.com">contact@illinoisjobtracker.com</a></p>
          <p className="mt-3">By accessing the Services, you agree to these Terms. Do not use the Services if you do not agree. The Services are intended for users age 18 or older.</p>
        </section>

        <nav className="mt-8 border border-border bg-card p-5" aria-label="Table of contents">
          <p className="kbd-label mb-3">Table of contents</p>
          <ol className="grid gap-2 text-sm sm:grid-cols-2">
            {sections.map(([id, title]) => <li key={id}><a className="text-primary underline underline-offset-4" href={`#${id}`}>{title}</a></li>)}
            <li><a className="text-primary underline underline-offset-4" href="#contact">27. Contact Us</a></li>
          </ol>
        </nav>

        {sections.map(([id, title, content]) => (
          <section id={id} className="mt-12 scroll-mt-6" key={id}>
            <h2 className="font-display text-2xl font-bold">{title}</h2>
            <p className="mt-3 leading-7">{content}</p>
            {id === "privacy" && <p className="mt-3">Review our <a className="font-medium text-primary underline underline-offset-4" href="/privacy-policy">Privacy Policy</a>.</p>}
          </section>
        ))}

        <section id="contact" className="mt-12 scroll-mt-6 border-t border-border pt-8">
          <h2 className="font-display text-2xl font-bold">27. Contact Us</h2>
          <p className="mt-3">KMG123 Enterprises LLC<br />4860 N Paulina St<br />Chicago, IL 60640<br />United States</p>
          <p className="mt-3">Phone: <a className="font-medium text-primary underline underline-offset-4" href="tel:+18003125555">1-800-312-5555</a><br />Email: <a className="font-medium text-primary underline underline-offset-4" href="mailto:contact@illinoisjobtracker.com">contact@illinoisjobtracker.com</a></p>
        </section>
      </article>
    </main>
  );
}
