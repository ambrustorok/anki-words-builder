import { Link } from "react-router-dom";

import { API_BASE_URL } from "../lib/api";

interface Props {
  deckId: string;
  className?: string;
  variant?: "inline" | "stacked";
}

export function DeckQuickActions({ deckId, className = "", variant = "inline" }: Props) {
  const containerClasses = [
    "flex flex-wrap gap-2",
    variant === "stacked" ? "mt-3 border-t border-slate-100 pt-3 dark:border-slate-800" : "",
    className
  ]
    .filter(Boolean)
    .join(" ");

  const iconButton =
    "inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 text-slate-500 transition hover:border-slate-400 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-500";

  const actions = [
    { label: "Add card", to: `/cards/new/${deckId}`, icon: IconPlus },
    { label: "View deck", to: `/decks/${deckId}`, icon: IconEye },
    { label: "Edit deck", to: `/decks/${deckId}/edit`, icon: IconEdit },
    { label: "Export to Anki", href: `${API_BASE_URL}/decks/${deckId}/export`, icon: IconDownload },
    { label: "Backup deck", href: `${API_BASE_URL}/decks/${deckId}/backup`, icon: IconArchive }
  ];

  return (
    <div className={containerClasses}>
      {actions.map((action) =>
        action.to ? (
          <Link
            key={action.label}
            className={`${iconButton} bg-white/50 dark:bg-slate-900/40`}
            to={action.to}
            title={action.label}
            aria-label={action.label}
            onClick={(event) => event.stopPropagation()}
            onKeyDown={(event) => event.stopPropagation()}
          >
            <action.icon />
          </Link>
        ) : (
          <a
            key={action.label}
            className={`${iconButton} bg-white/50 dark:bg-slate-900/40`}
            href={action.href}
            title={action.label}
            aria-label={action.label}
            onClick={(event) => event.stopPropagation()}
            onKeyDown={(event) => event.stopPropagation()}
          >
            <action.icon />
          </a>
        )
      )}
    </div>
  );
}

const iconProps = "h-4 w-4";

function IconPlus() {
  return (
    <svg className={iconProps} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round">
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </svg>
  );
}

function IconEye() {
  return (
    <svg className={iconProps} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round">
      <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function IconEdit() {
  return (
    <svg className={iconProps} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round">
      <path d="M4 17.5V20h2.5l11-11-2.5-2.5-11 11z" />
      <path d="M15 6l2.5 2.5" />
    </svg>
  );
}

function IconDownload() {
  return (
    <svg className={iconProps} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round">
      <path d="M12 5v12" />
      <path d="M7 12l5 5 5-5" />
      <path d="M5 19h14" />
    </svg>
  );
}

function IconArchive() {
  return (
    <svg className={iconProps} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round">
      <rect x="3" y="5" width="18" height="4" rx="1" />
      <path d="M5 9v10a1 1 0 001 1h12a1 1 0 001-1V9" />
      <path d="M9 13h6" />
    </svg>
  );
}
