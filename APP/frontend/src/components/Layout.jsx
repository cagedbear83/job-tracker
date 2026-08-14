import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useState } from "react";
import { useTheme } from "next-themes";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
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
  SunIcon,
  MoonIcon,
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

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role === "admin";
  const [drawerOpen, setDrawerOpen] = useState(false);
  const { theme, setTheme } = useTheme();

  const onLogout = async () => {
    await logout();
    navigate("/login");
  };

  const navItems = isAdmin ? adminNav : userNav;

  return (
    <div className="min-h-screen bg-background">
      <div className="brand-bar" />
      <header className="border-b border-border bg-background">
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
                  <div className="font-display font-black text-base">
                    Illinois UI Tracker
                  </div>
                  <div className="kbd-label mt-1">Work Search Compliance</div>
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
              </SheetContent>
            </Sheet>
            <div className="w-9 h-9 bg-primary flex items-center justify-center text-white font-display font-black tracking-tight">
              IL
            </div>
            <div>
              <div className="font-display font-black text-base leading-none tracking-tight text-foreground">
                Illinois UI Tracker
              </div>
              <div className="kbd-label mt-1">
                Work Search Compliance{isAdmin ? " · ADMIN" : ""}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4">
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

      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 py-6 grid grid-cols-12 gap-6">
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
          {/* Dark mode toggle */}
          <button
            type="button"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            className="mt-3 w-full flex items-center gap-2 px-4 py-2 text-xs text-muted-foreground hover:text-foreground hover:bg-secondary border-t border-border transition-colors"
            aria-label="Toggle dark mode"
          >
            {theme === "dark"
              ? <SunIcon size={14} weight="bold" />
              : <MoonIcon size={14} weight="bold" />}
            {theme === "dark" ? "Light mode" : "Dark mode"}
          </button>

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
    </div>
  );
}