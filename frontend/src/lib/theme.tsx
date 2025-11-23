import { createContext, useContext, useEffect, useState } from "react";

type Theme = "light" | "dark";

const ThemeContext = createContext<Theme | null>(null);

function getPreferredTheme(): Theme {
  if (typeof window === "undefined") {
    return "light";
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>(getPreferredTheme);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const listener = (event: MediaQueryListEvent) => {
      setTheme(event.matches ? "dark" : "light");
    };
    media.addEventListener("change", listener);
    return () => media.removeEventListener("change", listener);
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  }, [theme]);

  return <ThemeContext.Provider value={theme}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("ThemeContext unavailable");
  }
  return ctx;
}
