import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { MoonIcon, SunIcon } from "@phosphor-icons/react";

/**
 * Matches the toggle in ijt-marketing/components/site-nav.tsx — same icons,
 * same geometry, same always-visible placement in the header. It used to live
 * in the desktop sidebar, which meant no theme control at all below `md`.
 *
 * Drives off resolvedTheme (what is actually on screen) rather than `theme`,
 * which can be the literal "system". `mounted` guards the first client paint so
 * the icon cannot disagree with the rendered colors.
 */
export default function ThemeToggle({ variant = "icon", className = "" }) {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const isDark = mounted && resolvedTheme === "dark";

  const label = isDark ? "Switch to light mode" : "Switch to dark mode";
  const Icon = isDark ? SunIcon : MoonIcon;

  if (variant === "full") {
    return (
      <button
        type="button"
        onClick={() => setTheme(isDark ? "light" : "dark")}
        aria-label={label}
        data-testid="theme-toggle"
        className={`w-full flex items-center gap-3 px-4 py-3 text-sm text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors ${className}`}
      >
        <Icon size={18} weight="bold" />
        <span>{isDark ? "Light mode" : "Dark mode"}</span>
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={label}
      data-testid="theme-toggle"
      className={`grid h-9 w-9 place-items-center border border-border text-muted-foreground transition-colors hover:border-primary hover:text-primary ${className}`}
    >
      <Icon size={16} weight="bold" />
    </button>
  );
}
