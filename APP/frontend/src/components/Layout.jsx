import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useState } from "react";
import { useTheme } from "next-themes";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import {
  HouseIcon,
  IdentificationCardIcon,
  CalendarBlankIcon,
  UploadSimpleIcon,
  ClockCounterClockwiseIcon,
  SignOutIcon,
  UsersThreeIcon,
  ShieldCheckIcon,
  CalendarCheckIcon,
  ListIcon,
  FolderOpenIcon,
  SunIcon,
  MoonIcon,
} from "@phosphor-icons/react";
import { toast } from "sonner";

const userNav = [
  {
    to: "/dashboard",
    label: "Dashboard",
    Icon: HouseIcon,
    testid: "nav-dashboard",
  },
  {
    to: "/claimants",
    label: "Claimants",
    Icon: UsersThreeIcon,
    testid: "nav-claimants",
  },
  {
    to: "/profile",
    label: "Quick Profile",
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
  const { user, logout, claimants, activeClaimantId, setActiveClaimant } =
    useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role === "admin";
  const [drawerOpen, setDrawerOpen] = useState(false);
  const { theme, setTheme } = useTheme();

  const onLogout = async () => {
    await logout();
    navigate("/login");
  };

  const onSwitch = async (id) => {
    try {
      await setActiveClaimant(id);
      toast.success("Switched claimant");
      window.location.reload();
    } catch (e) {
      toast.error("Could not switch claimant");
    }
  };

  const navItems = isAdmin ? adminNav : userNav;
  const activeClaimant = claimants.find((c) => c.id === activeClaimantId);

  return (
    <div className="min-h-screen bg-white">
      <div className="brand-bar" />
      <header className="border-b border-zinc-200 bg-white">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
              <SheetTrigger asChild>
                <Button
                  variant="outline"
                  size="icon"
                  className="rounded-none border-zinc-300 md:hidden"
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
                <div className="px-4 py-4 border-b border-zinc-200">
                  <div className="font-display font-black text-base">
                    Illinois UI Tracker
                  </div>
                  <div className="kbd-label mt-1">Work Search Compliance</div>
                </div>
                <nav className="border-b border-zinc-200">
                  {navItems.map(({ to, label, Icon, testid }) => (
                    <NavLink
                      key={to}
                      to={to}
                      onClick={() => setDrawerOpen(false)}
                      data-testid={`m-${testid}`}
                      className={({ isActive }) =>
                        `flex items-center gap-3 px-4 py-3 text-sm border-l-2 ${
                          isActive
                            ? "border-[#0033A0] bg-[#F4F4F5] text-zinc-900 font-semibold"
                            : "border-transparent text-zinc-600"
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
            <div className="w-9 h-9 bg-[#0033A0] flex items-center justify-center text-white font-display font-black tracking-tight">
              IL
            </div>
            <div>
              <div className="font-display font-black text-base leading-none tracking-tight text-zinc-900">
                Illinois UI Tracker
              </div>
              <div className="kbd-label mt-1">
                Work Search Compliance{isAdmin ? " · ADMIN" : ""}
              </div>
            </div>
          </div>

          {!isAdmin && claimants.length > 0 && (
            <div
              className="flex items-center gap-2"
              data-testid="active-claimant-switcher"
            >
              <span className="kbd-label">Claimant:</span>
              <Select value={activeClaimantId || ""} onValueChange={onSwitch}>
                <SelectTrigger
                  className="rounded-none border-zinc-300 min-w-[200px]"
                  data-testid="claimant-select-trigger"
                >
                  <SelectValue placeholder="Select claimant">
                    {activeClaimant
                      ? `${activeClaimant.label || "Untitled"} — ${activeClaimant.first_name} ${activeClaimant.last_name}`
                      : "Select"}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {claimants.map((c) => (
                    <SelectItem
                      key={c.id}
                      value={c.id}
                      data-testid={`claimant-option-${c.id}`}
                    >
                      {c.label || "Untitled"} — {c.first_name} {c.last_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="flex items-center gap-4">
            <div className="text-right hidden sm:block">
              <div
                className="text-sm font-semibold text-zinc-900"
                data-testid="header-user-name"
              >
                {user?.name}
              </div>
              <div className="kbd-label">{user?.email}</div>
            </div>
            <Button
              variant="outline"
              className="rounded-none border-zinc-300 hover:border-[#0033A0] hover:text-[#0033A0]"
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
          <nav className="border border-zinc-200 bg-white">
            {navItems.map(({ to, label, Icon, testid }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/dashboard"}
                data-testid={testid}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-4 py-3 text-sm border-l-2 transition-colors ${
                    isActive
                      ? "border-[#0033A0] bg-[#F4F4F5] text-zinc-900 font-semibold"
                      : "border-transparent text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900"
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
            className="mt-3 w-full flex items-center gap-2 px-4 py-2 text-xs text-zinc-500 hover:text-zinc-900 hover:bg-zinc-50 border-t border-zinc-200 transition-colors"
            aria-label="Toggle dark mode"
          >
            {theme === "dark"
              ? <SunIcon size={14} weight="bold" />
              : <MoonIcon size={14} weight="bold" />}
            {theme === "dark" ? "Light mode" : "Dark mode"}
          </button>

          {!isAdmin && (
            <div className="mt-4 p-4 border border-zinc-200 bg-[#F4F4F5] dark:bg-zinc-800 dark:border-zinc-700">
              <div className="kbd-label mb-1">Reminder</div>
              <p className="text-xs text-zinc-700 dark:text-zinc-300 leading-relaxed">
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
