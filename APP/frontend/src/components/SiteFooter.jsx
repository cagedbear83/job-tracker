import Logo from "@/components/Logo";
import { site, marketingUrl } from "@/lib/site";

// Mirrors ijt-marketing/components/site-footer.tsx. Every link points back at
// the marketing site, which owns all marketing and legal content — this is the
// return path out of the app, which previously did not exist anywhere.
const columns = [
  {
    title: "Product",
    links: [
      { label: "Features", href: "/features" },
      { label: "How It Works", href: "/how-it-works" },
      { label: "Pricing", href: "/pricing" },
      { label: "FAQ", href: "/faq" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About", href: "/about" },
      { label: "Contact", href: "/contact" },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Privacy Policy", href: "/privacy" },
      { label: "Terms of Service", href: "/terms" },
      { label: "Refund Policy", href: "/refunds" },
      { label: "IDES Disclaimer", href: "/disclaimer" },
    ],
  },
];

const linkClass =
  "text-sm text-muted-foreground transition-colors hover:text-foreground";

export default function SiteFooter() {
  return (
    <footer className="border-t border-border bg-surface mt-12">
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 py-12">
        <div className="grid gap-8 sm:grid-cols-2 md:grid-cols-4">
          <div>
            <a
              href={marketingUrl("/")}
              className="text-sm"
              aria-label={site.name}
            >
              <Logo size={32} />
            </a>
            <p className="mt-3 text-sm text-muted-foreground">{site.tagline}</p>
          </div>

          {columns.map((col) => (
            <div key={col.title}>
              <h3 className="text-sm font-semibold font-display">
                {col.title}
              </h3>
              <ul className="mt-3 space-y-2">
                {col.links.map((l) => (
                  <li key={l.href}>
                    <a href={marketingUrl(l.href)} className={linkClass}>
                      {l.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-10 border border-border bg-background p-4 text-xs text-muted-foreground">
          <strong className="text-foreground">Not a government service.</strong>{" "}
          {site.name} is an independent tool operated by {site.company}. It is
          not affiliated with, endorsed by, or connected to the Illinois
          Department of Employment Security (IDES) or any government agency. You
          are solely responsible for the accuracy and timeliness of any
          information you submit to IDES.
        </div>

        <p className="mt-6 text-xs text-muted-foreground">
          © {new Date().getFullYear()} {site.company}. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
