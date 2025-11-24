import { NavLink, Link, useLocation } from "react-router-dom";
import { ReactNode, useEffect, useState } from "react";
import { useSession } from "../lib/session";
import { getCloudflareLogoutUrl } from "../lib/logout";

interface LayoutProps {
  children: ReactNode;
}

const desktopLinkClasses =
  "px-3 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white";
const mobileLinkClasses =
  "block rounded-lg px-3 py-2 text-base font-semibold text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800";

export function Layout({ children }: LayoutProps) {
  const session = useSession();
  const user = session.data?.user;
  const logoutHref = getCloudflareLogoutUrl();
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  const navItems = [
    { to: "/", label: "Dashboard" },
    { to: "/decks", label: "Decks" },
    { to: "/profile", label: "Profile" },
    ...(user?.isAdmin ? [{ to: "/admin/users", label: "Admin" }] : [])
  ];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 transition-colors dark:bg-slate-950 dark:text-slate-100">
      <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900/70">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
          <Link to="/" className="text-lg font-semibold text-slate-900 dark:text-white">
            Anki Words Builder
          </Link>
          <div className="flex items-center gap-3">
            <nav className="hidden items-center gap-2 text-slate-600 md:flex dark:text-slate-300">
              {navItems.map((item) => (
                <NavLink key={item.to} className={desktopLinkClasses} to={item.to}>
                  {item.label}
                </NavLink>
              ))}
              {logoutHref && (
                <a
                  className="rounded-full bg-slate-900 px-3 py-2 text-sm font-semibold text-white dark:bg-white dark:text-slate-900"
                  href={logoutHref}
                >
                  Log out
                </a>
              )}
            </nav>
            <button
              type="button"
              className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 text-slate-600 transition hover:border-slate-400 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-500 md:hidden"
              onClick={() => setMenuOpen((open) => !open)}
              aria-label="Toggle navigation menu"
              aria-expanded={menuOpen}
            >
              <span className="sr-only">Toggle menu</span>
              {menuOpen ? (
                <svg className="h-5 w-5" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round">
                  <path d="M6 18L18 6" />
                  <path d="M6 6l12 12" />
                </svg>
              ) : (
                <svg className="h-5 w-5" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round">
                  <path d="M4 7h16" />
                  <path d="M4 12h16" />
                  <path d="M4 17h16" />
                </svg>
              )}
            </button>
          </div>
        </div>
        {menuOpen && (
          <div className="border-t border-slate-200 bg-white px-4 py-4 shadow-md dark:border-slate-800 dark:bg-slate-900 md:hidden">
            <nav className="space-y-1">
              {navItems.map((item) => (
                <NavLink key={item.to} className={mobileLinkClasses} to={item.to}>
                  {item.label}
                </NavLink>
              ))}
              {logoutHref && (
                <a className={`${mobileLinkClasses} bg-slate-900 text-white dark:bg-white dark:text-slate-900`} href={logoutHref}>
                  Log out
                </a>
              )}
            </nav>
          </div>
        )}
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">{children}</main>
    </div>
  );
}
