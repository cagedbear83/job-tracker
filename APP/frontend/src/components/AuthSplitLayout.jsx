/**
 * The split-screen frame the sign-in and sign-up pages share.
 *
 * Lifted verbatim from the old hand-built Login/Register pages so adopting
 * Clerk didn't cost the page design — only the form inside the right column
 * changed, from our own inputs to Clerk's component.
 */
export default function AuthSplitLayout({ eyebrow, title, children }) {
  return (
    <div className="flex-1 grid grid-cols-1 md:grid-cols-2 bg-background">
      <div className="hidden md:block relative">
        <img
          src="https://images.unsplash.com/photo-1657639789999-837194c7d6aa?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA2MDV8MHwxfHNlYXJjaHwxfHxpbGxpbm9pcyUyMGNoaWNhZ28lMjBza3lsaW5lfGVufDB8fHx8MTc3ODU0ODUxN3ww&ixlib=rb-4.1.0&q=85"
          alt="Chicago Skyline"
          className="w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-primary/55" />
        <div className="absolute inset-0 p-12 flex flex-col justify-between text-white">
          <div className="brand-bar w-32" />
          <div>
            <div className="kbd-label text-white/70">State of Illinois</div>
            <h1 className="font-display font-black text-5xl lg:text-6xl tracking-tighter mt-2">
              Job Search
              <br />
              Tracker
            </h1>
            <p className="text-white/80 mt-4 max-w-md leading-relaxed">
              Stay compliant with Illinois Unemployment Insurance work-search
              requirements. Log contacts, certify weeks, and export IDES-style
              reports.
            </p>
          </div>
          <div className="text-xs text-white/60">
            Unofficial tool — not affiliated with IDES. Mirrors ADJ034F form
            structure.
          </div>
        </div>
      </div>

      <div className="flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <div className="mb-6">
            <div className="brand-bar w-20 mb-4" />
            <div className="kbd-label">{eyebrow}</div>
            <h2 className="font-display font-black text-3xl tracking-tighter mt-1">
              {title}
            </h2>
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}
