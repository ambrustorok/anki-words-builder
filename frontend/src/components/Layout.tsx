import { NavLink, Link } from "react-router-dom";
import { ReactNode } from "react";
import { useSession } from "../lib/session";
import { getCloudflareLogoutUrl } from "../lib/logout";

interface LayoutProps {
  children: ReactNode;
}

const linkClasses =
  "px-3 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white";

export function Layout({ children }: LayoutProps) {
  const session = useSession();
  const user = session.data?.user;
  const logoutHref = getCloudflareLogoutUrl();
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 transition-colors dark:bg-slate-950 dark:text-slate-100">
      <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900/70">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link to="/" className="text-lg font-semibold text-slate-900 dark:text-white">
            Anki Words Builder
          </Link>
          <nav className="flex items-center gap-3 text-slate-600 dark:text-slate-300">
            <NavLink className={linkClasses} to="/">
              Dashboard
            </NavLink>
            <NavLink className={linkClasses} to="/decks">
              Decks
            </NavLink>
            <NavLink className={linkClasses} to="/profile">
              Profile
            </NavLink>
            {user?.isAdmin && (
              <NavLink className={linkClasses} to="/admin/users">
                Admin
              </NavLink>
            )}
            {logoutHref && (
              <a
                className="rounded-full bg-slate-900 px-3 py-2 text-sm font-semibold text-white dark:bg-white dark:text-slate-900"
                href={logoutHref}
              >
                Log out
              </a>
            )}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
    </div>
  );
}
