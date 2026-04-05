import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
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

function applyTheme(resolved: ResolvedTheme) {
  if (resolved === "dark") {
    document.documentElement.classList.add("dark");
  } else {
    document.documentElement.classList.remove("dark");
  }
}

interface ThemeProviderProps {
  children: React.ReactNode;
  serverPreference?: ThemePreference;
}

export function ThemeProvider({ children, serverPreference }: ThemeProviderProps) {
  const [preference, setPreferenceState] = useState<ThemePreference>(() => {
    try {
      const stored = localStorage.getItem("theme-preference") as ThemePreference | null;
      if (stored && ["light", "dark", "system"].includes(stored)) return stored;
    } catch {}
    return "system";
  });

  // Track whether we've done the one-time server sync.
  // Once synced we never let the server value overwrite local changes.
  const serverSyncedRef = useRef(false);

  useEffect(() => {
    if (!serverPreference) return;
    if (serverSyncedRef.current) return; // already synced once — user owns it now
    serverSyncedRef.current = true;
    setPreferenceState(serverPreference);
    try { localStorage.setItem("theme-preference", serverPreference); } catch {}
  }, [serverPreference]);

  // Apply to DOM whenever preference changes
  useEffect(() => {
    applyTheme(resolveTheme(preference));
  }, [preference]);

  // Track OS-level changes when in system mode
  useEffect(() => {
    if (preference !== "system") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const listener = () => applyTheme(getSystemTheme());
    media.addEventListener("change", listener);
    return () => media.removeEventListener("change", listener);
  }, [preference]);

  const setPreference = useCallback((p: ThemePreference) => {
    setPreferenceState(p);
    try { localStorage.setItem("theme-preference", p); } catch {}
    apiFetch("/profile/theme", { method: "PUT", json: { theme: p } }).catch(() => {});
  }, []);

  const resolved: ResolvedTheme = resolveTheme(preference);

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
