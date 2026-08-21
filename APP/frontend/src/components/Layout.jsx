import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import Logo from "@/components/Logo";
import SiteFooter from "@/components/SiteFooter";
import ThemeToggle from "@/components/ThemeToggle";
import { site } from "@/lib/site";
import {
  HouseIcon,
  IdentificationCardIcon,
  CalendarBlankIcon,
  UploadSimpleIcon,
  ClockCounterClockwiseIcon,
  SignOutIcon,
  ShieldCheckIcon,
  CalendarCheckIcon,
  ListIcon,
  FolderOpenIcon,
  GearSixIcon,
} from "@phosphor-icons/react";

const userNav = [
  {
    to: "/dashboard",
    label: "Dashboard",
    Icon: HouseIcon,
    testid: "nav-dashboard",
  },
  {
    to: "/profile",
    label: "Profile",
    Icon: IdentificationCardIcon,
    testid: "nav-profile",
  },
  {
    to: "/weeks",
    label: "Benefit Weeks",
    Icon: CalendarBlankIcon,
    testid: "nav-weeks",
  },
  {
    to: "/calendar",
    label: "Calendar",
    Icon: CalendarCheckIcon,
    testid: "nav-calendar",
  },
  {
    to: "/documents",
    label: "My Documents",
    Icon: FolderOpenIcon,
    testid: "nav-documents",
  },
  {
    to: "/import",
    label: "Import",
    Icon: UploadSimpleIcon,
    testid: "nav-import",
  },
  {
    to: "/audit",
    label: "Audit Log",
    Icon: ClockCounterClockwiseIcon,
    testid: "nav-audit",
  },
];

const adminNav = [
  { to: "/admin", label: "Admin", Icon: ShieldCheckIcon, testid: "nav-admin" },
  {
    to: "/audit",
    label: "Audit Log",
    Icon: ClockCounterClockwiseIcon,
    testid: "nav-audit",
  },
];

// Link to the new admin-platform surface (src/pages/AdminPlatform.jsx).
// Shown separately from adminNav/userNav since it's gated on platform_role
// (support_staff or platform_admin), not the legacy binary role field.
const platformNavItem = {
  to: "/admin/platform",
  label: "Admin Platform",
  Icon: GearSixIcon,
  testid: "nav-admin-platform",
};

// Mirrors rbac.py's legacy-role fallback and App.jsx's platformRoleFor():
// treats role === "admin" as platform_admin until platform_role is backfilled.
function platformRoleFor(user) {
  if (user?.platform_role) return user.platform_role;
  return user?.role === "admin" ? "platform_admin" : "user";
}

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role === "admin";
  const [drawerOpen, setDrawerOpen] = useState(false);

  const onLogout = async () => {
    await logout();
    navigate("/login");
  };

  const platformRole = platformRoleFor(user);
  const canSeePlatformAdmin =
    platformRole === "support_staff" || platformRole === "platform_admin";

  const navItems = [
    ...(isAdmin ? adminNav : userNav),
    ...(canSeePlatformAdmin ? [platformNavItem] : []),
  ];

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <div className="brand-bar" />
      {/* Sticky + blurred to match the marketing site nav. */}
      <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
              <SheetTrigger asChild>
                <Button
                  variant="outline"
                  size="icon"
                  className="rounded-none border-border md:hidden"
                  data-testid="mobile-nav-trigger"
                >
                  <ListIcon size={18} weight="bold" />
                </Button>
              </SheetTrigger>
              <SheetContent
                side="left"
                className="w-[280px] rounded-none p-0"
                data-testid="mobile-nav-drawer"
              >
                <div className="brand-bar" />
                <div className="px-4 py-4 border-b border-border">
                  <Logo size={32} className="text-base" />
                  <div className="kbd-label mt-2">Work Search Compliance</div>
                </div>
                <nav className="border-b border-border">
                  {navItems.map(({ to, label, Icon, testid }) => (
                    <NavLink
                      key={to}
                      to={to}
                      onClick={() => setDrawerOpen(false)}
                      data-testid={`m-${testid}`}
                      className={({ isActive }) =>
                        `flex items-center gap-3 px-4 py-3 text-sm border-l-2 ${
                          isActive
                            ? "border-primary bg-secondary text-foreground font-semibold"
                            : "border-transparent text-muted-foreground"
                        }`
                      }
                    >
                      <Icon size={18} weight="bold" />
                      <span>{label}</span>
                    </NavLink>
                  ))}
                </nav>
                <ThemeToggle variant="full" className="border-b border-border" />
              </SheetContent>
            </Sheet>
            <Link
              to="/dashboard"
              className="flex items-center gap-3"
              aria-label={site.name}
            >
              <Logo size={32} showWordmark={false} />
              <div>
                <div className="font-display font-black text-base leading-none tracking-tight text-foreground">
                  {site.name}
                </div>
                <div className="kbd-label mt-1">
                  Work Search Compliance{isAdmin ? " · ADMIN" : ""}
                </div>
              </div>
            </Link>
          </div>

          <div className="flex items-center gap-3">
            <ThemeToggle />
            <div className="text-right hidden sm:block">
              <div
                className="text-sm font-semibold text-foreground"
                data-testid="header-user-name"
              >
                {user?.name}
              </div>
              <div className="kbd-label">{user?.email}</div>
            </div>
            <Button
              variant="outline"
              className="rounded-none border-border hover:border-primary hover:text-primary"
              onClick={onLogout}
              data-testid="logout-button"
            >
              <SignOutIcon className="mr-2" size={16} weight="bold" /> Logout
            </Button>
          </div>
        </div>
      </header>

      <div className="flex-1 w-full max-w-[1440px] mx-auto px-4 sm:px-6 py-6 grid grid-cols-12 gap-6">
        <aside className="hidden md:block col-span-12 md:col-span-3 lg:col-span-2">
          <nav className="border border-border bg-background">
            {navItems.map(({ to, label, Icon, testid }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/dashboard"}
                data-testid={testid}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-4 py-3 text-sm border-l-2 transition-colors ${
                    isActive
                      ? "border-primary bg-secondary text-foreground font-semibold"
                      : "border-transparent text-muted-foreground hover:bg-secondary hover:text-foreground"
                  }`
                }
              >
                <Icon size={18} weight="bold" />
                <span>{label}</span>
              </NavLink>
            ))}
          </nav>
          {!isAdmin && (
            <div className="mt-4 p-4 border border-border bg-secondary">
              <div className="kbd-label mb-1">Reminder</div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Illinois requires a minimum of <b>3 work-search contacts</b> per
                benefit week (Sun–Sat).
              </p>
            </div>
          )}
        </aside>

        <main className="col-span-12 md:col-span-9 lg:col-span-10">
          <Outlet />
        </main>
      </div>

      <SiteFooter />
    </div>
  );
}