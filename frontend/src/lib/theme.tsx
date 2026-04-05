import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { apiFetch } from "./api";

export type ThemePreference = "light" | "dark" | "system";
type ResolvedTheme = "light" | "dark";

interface ThemeContextValue {
  preference: ThemePreference;
  resolved: ResolvedTheme;
  setPreference: (p: ThemePreference) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function getSystemTheme(): ResolvedTheme {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function resolveTheme(preference: ThemePreference): ResolvedTheme {
  if (preference === "system") return getSystemTheme();
  return preference;
}

/** Apply / remove the `dark` class on <html> immediately. */
function applyTheme(resolved: ResolvedTheme) {
  if (resolved === "dark") {
    document.documentElement.classList.add("dark");
  } else {
    document.documentElement.classList.remove("dark");
  }
}

interface ThemeProviderProps {
  children: React.ReactNode;
  /** Server-supplied preference — passed in from SessionData once loaded. */
  serverPreference?: ThemePreference;
}

export function ThemeProvider({ children, serverPreference }: ThemeProviderProps) {
  // Boot from localStorage first so the page never flashes the wrong colour
  // while the session loads. Then upgrade to the server value once available.
  const [preference, setPreferenceState] = useState<ThemePreference>(() => {
    try {
      const stored = localStorage.getItem("theme-preference") as ThemePreference | null;
      if (stored && ["light", "dark", "system"].includes(stored)) return stored;
    } catch {}
    return "system";
  });

  // Once the server preference arrives, honour it (and mirror it to localStorage)
  useEffect(() => {
    if (!serverPreference) return;
    setPreferenceState(serverPreference);
    try { localStorage.setItem("theme-preference", serverPreference); } catch {}
  }, [serverPreference]);

  const [resolved, setResolved] = useState<ResolvedTheme>(() => resolveTheme(preference));

  // Keep resolved in sync with preference
  useEffect(() => {
    const r = resolveTheme(preference);
    setResolved(r);
    applyTheme(r);
  }, [preference]);

  // Track system theme changes when preference === 'system'
  useEffect(() => {
    if (preference !== "system") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const listener = (e: MediaQueryListEvent) => {
      const r: ResolvedTheme = e.matches ? "dark" : "light";
      setResolved(r);
      applyTheme(r);
    };
    media.addEventListener("change", listener);
    return () => media.removeEventListener("change", listener);
  }, [preference]);

  const setPreference = useCallback((p: ThemePreference) => {
    setPreferenceState(p);
    try { localStorage.setItem("theme-preference", p); } catch {}
    // Persist to server (fire-and-forget — not critical)
    apiFetch("/profile/theme", { method: "PUT", json: { theme: p } }).catch(() => {});
  }, []);

  return (
    <ThemeContext.Provider value={{ preference, resolved, setPreference }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("ThemeContext unavailable");
  return ctx;
}
