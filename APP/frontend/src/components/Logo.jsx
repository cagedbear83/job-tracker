import { site } from "@/lib/site";

/**
 * The brand lockup. The mark is /icons/logo-mark.svg — the exact same file
 * illinoisjobtracker.com serves, generated from APP/brand/logo-mark.svg — so
 * the identity does not shift when a visitor crosses between the two domains.
 *
 * `to` is a plain href because the marketing site lives on another origin;
 * callers pass a router <Link> wrapper when they need in-app navigation.
 */
export default function Logo({
  size = 32,
  showWordmark = true,
  className = "",
}) {
  return (
    <span className={`flex items-center gap-2 ${className}`}>
      <img
        src="/icons/logo-mark.svg"
        alt=""
        width={size}
        height={size}
        style={{ width: size, height: size }}
      />
      {showWordmark && (
        <span className="font-display font-black tracking-tight">
          {site.name}
        </span>
      )}
    </span>
  );
}
