import { useTheme, ThemePreference } from "../lib/theme";

const OPTIONS: { value: ThemePreference; label: string; icon: string }[] = [
  { value: "light", label: "Light", icon: "☀️" },
  { value: "system", label: "Auto", icon: "💻" },
  { value: "dark", label: "Dark", icon: "🌙" },
];

interface ThemeToggleProps {
  /** "pills" = segmented control (default), "select" = native <select> */
  variant?: "pills" | "select";
}

export function ThemeToggle({ variant = "pills" }: ThemeToggleProps) {
  const { preference, setPreference } = useTheme();

  if (variant === "select") {
    return (
      <select
        value={preference}
        onChange={(e) => setPreference(e.target.value as ThemePreference)}
        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-white"
      >
        {OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>{o.icon} {o.label}</option>
        ))}
      </select>
    );
  }

  return (
    <div className="inline-flex overflow-hidden rounded-full border border-slate-200 text-xs dark:border-slate-700">
      {OPTIONS.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => setPreference(o.value)}
          title={o.label}
          aria-pressed={preference === o.value}
          className={`flex items-center gap-1 px-3 py-2 font-medium transition min-h-[36px] ${
            preference === o.value
              ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900"
              : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100"
          }`}
        >
          <span>{o.icon}</span>
          <span className="hidden sm:inline">{o.label}</span>
        </button>
      ))}
    </div>
  );
}
