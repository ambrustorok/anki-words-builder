import { NavLink, Link, useLocation } from "react-router-dom";
import { ReactNode } from "react";
import { useSession } from "../lib/session";
import { getCloudflareLogoutUrl } from "../lib/logout";
import { ThemeToggle } from "./ThemeToggle";

interface LayoutProps {
  children: ReactNode;
}

// SVG icons for bottom nav
const icons = {
  home: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-6 w-6">
      <path d="M3 12L12 3l9 9" /><path d="M9 21V12h6v9" /><path d="M3 12v9h18v-9" />
    </svg>
  ),
  decks: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-6 w-6">
      <rect x="2" y="7" width="20" height="14" rx="2" /><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" />
    </svg>
  ),
  profile: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-6 w-6">
      <circle cx="12" cy="8" r="4" /><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
    </svg>
  ),
  help: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-6 w-6">
      <circle cx="12" cy="12" r="10" /><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3" /><circle cx="12" cy="17" r=".5" fill="currentColor" />
    </svg>
  ),
  admin: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-6 w-6">
      <path d="M12 2l3 6.5L22 10l-5 4.9L18.1 22 12 18.8 5.9 22 7 14.9 2 10l7-1.5L12 2z" />
    </svg>
  ),
};

export function Layout({ children }: LayoutProps) {
  const session = useSession();
  const user = session.data?.user;
  const logoutHref = getCloudflareLogoutUrl();
  const location = useLocation();

  type NavItem = { to: string; label: string; icon: ReactNode };
  const navItems: NavItem[] = [
    { to: "/", label: "Home", icon: icons.home },
    { to: "/decks", label: "Decks", icon: icons.decks },
    { to: "/profile", label: "Profile", icon: icons.profile },
    { to: "/help", label: "Help", icon: icons.help },
    ...(user?.isAdmin ? [{ to: "/admin/users", label: "Admin", icon: icons.admin }] : []),
  ];

  const isActive = (to: string) =>
    to === "/" ? location.pathname === "/" : location.pathname.startsWith(to);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      {/* Desktop top bar */}
      <header className="hidden md:block border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900/70">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
          <Link to="/" className="text-base font-semibold text-slate-900 dark:text-white">
            Anki Words Builder
          </Link>
          <nav className="flex items-center gap-1 text-sm text-slate-600 dark:text-slate-300">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  `px-3 py-2 rounded-lg font-medium transition ${
                    isActive
                      ? "bg-slate-100 text-slate-900 dark:bg-slate-800 dark:text-white"
                      : "hover:bg-slate-50 dark:hover:bg-slate-800/50"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
            <ThemeToggle />
            {logoutHref && (
              <a
                className="ml-2 rounded-full bg-slate-900 px-3 py-2 text-sm font-semibold text-white dark:bg-white dark:text-slate-900"
                href={logoutHref}
              >
                Log out
              </a>
            )}
          </nav>
        </div>
      </header>

      {/* Mobile top bar — app name + theme toggle */}
      <header className="md:hidden border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900/70">
        <div className="flex items-center justify-between px-4 py-3">
          <Link to="/" className="text-base font-semibold text-slate-900 dark:text-white">
            Anki Words Builder
          </Link>
          <ThemeToggle />
        </div>
      </header>

      {/* Page content — pad bottom on mobile for tab bar */}
      <main className="mx-auto max-w-3xl px-3 py-5 pb-24 sm:px-4 md:pb-8">
        {children}
      </main>

      {/* Mobile bottom tab bar */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-50 border-t border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <div className="flex">
          {navItems.map((item) => {
            const active = isActive(item.to);
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`flex flex-1 flex-col items-center gap-0.5 py-2.5 text-[10px] font-medium transition ${
                  active
                    ? "text-brand"
                    : "text-slate-400 dark:text-slate-500"
                }`}
              >
                <span className={active ? "text-brand" : "text-slate-400 dark:text-slate-500"}>
                  {item.icon}
                </span>
                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
