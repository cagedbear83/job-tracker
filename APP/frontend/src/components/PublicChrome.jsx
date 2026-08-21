import ThemeToggle from "@/components/ThemeToggle";
import { site, marketingUrl } from "@/lib/site";

const links = [
  { label: "Pricing", href: "/pricing" },
  { label: "FAQ", href: "/faq" },
  { label: "Privacy", href: "/privacy" },
  { label: "Terms", href: "/terms" },
];

/**
 * Wraps every signed-out page (login, register, password reset, invite,
 * verify). These render outside Layout, which used to mean no full-width brand
 * bar, no way back to illinoisjobtracker.com, and — because the theme toggle
 * lived in the desktop sidebar — no theme control at all.
 */
export default function PublicChrome({ children }) {
  return (
    <div className="min-h-screen flex flex-col bg-background">
      <div className="brand-bar" />

      <div className="flex-1 flex flex-col">{children}</div>

      <footer className="border-t border-border bg-surface">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 py-4 flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
            <a
              href={marketingUrl("/")}
              className="font-semibold text-foreground transition-colors hover:text-primary"
            >
              ← {site.name}
            </a>
            {links.map((l) => (
              <a
                key={l.href}
                href={marketingUrl(l.href)}
                className="transition-colors hover:text-foreground"
              >
                {l.label}
              </a>
            ))}
          </div>
          <ThemeToggle />
        </div>
      </footer>
    </div>
  );
}
