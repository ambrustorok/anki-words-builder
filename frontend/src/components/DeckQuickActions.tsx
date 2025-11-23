import { Link } from "react-router-dom";

import { API_BASE_URL } from "../lib/api";

interface Props {
  deckId: string;
  className?: string;
  variant?: "inline" | "stacked";
}

export function DeckQuickActions({ deckId, className = "", variant = "inline" }: Props) {
  const baseButton =
    "rounded-full border border-slate-300 px-3 py-1 text-xs font-semibold text-slate-700 transition hover:border-slate-400 hover:text-slate-900 dark:border-slate-600 dark:text-slate-200 dark:hover:border-slate-500";
  const containerClasses = [
    "flex flex-wrap gap-2",
    variant === "stacked" ? "mt-3 border-t border-slate-100 pt-3 dark:border-slate-800" : "",
    className
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={containerClasses}>
      <Link className={`${baseButton} bg-brand/30 border-brand/40 text-slate-900`} to={`/cards/new/${deckId}`}>
        New card
      </Link>
      <Link className={baseButton} to={`/decks/${deckId}`}>
        View
      </Link>
      <Link className={baseButton} to={`/decks/${deckId}/edit`}>
        Edit
      </Link>
      <a className={baseButton} href={`${API_BASE_URL}/decks/${deckId}/export`}>
        Export .apkg
      </a>
      <a className={baseButton} href={`${API_BASE_URL}/decks/${deckId}/backup`}>
        Backup
      </a>
    </div>
  );
}
