import { ChangeEvent, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";

import { apiFetch } from "../lib/api";
import { LoadingScreen } from "../components/LoadingScreen";
import { useSession } from "../lib/session";
import { DeckQuickActions } from "../components/DeckQuickActions";

interface DeckListResponse {
  decks: any[];
}

export function DeckListPage() {
  const session = useSession();
  const navigate = useNavigate();
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["decks"],
    queryFn: () => apiFetch<DeckListResponse>("/decks")
  });

  if (isLoading) {
    return <LoadingScreen label="Loading decks" />;
  }
  if (error) {
    return <p className="text-red-500">Failed to load decks: {(error as Error).message}</p>;
  }

  const triggerImport = () => {
    setImportError("");
    fileInputRef.current?.click();
  };

  const handleImportChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setImportError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await apiFetch<{ deck: { id: string } }>("/decks/import", {
        method: "POST",
        body: formData
      });
      await refetch();
      navigate(`/decks/${response.deck.id}`);
    } catch (err) {
      setImportError((err as Error).message);
    } finally {
      setImporting(false);
      event.target.value = "";
    }
  };

  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
      <div className="flex flex-wrap items-start gap-4">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-white">Decks</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Review your study sets, edit prompts, or export backups in one place.
          </p>
        </div>
        <div className="ml-auto flex flex-wrap gap-2">
          {session.data?.needsOnboarding ? (
            <Link to="/onboarding" className="rounded-full border border-slate-300 px-4 py-2 text-sm dark:border-slate-600 dark:text-slate-200">
              Finish onboarding
            </Link>
          ) : (
            <Link to="/decks/new" className="rounded-full bg-brand px-4 py-2 text-sm font-semibold text-slate-900">
              New deck
            </Link>
          )}
          <button
            type="button"
            className="rounded-full border border-slate-300 px-4 py-2 text-sm dark:border-slate-600 dark:text-slate-200 disabled:opacity-60"
            onClick={triggerImport}
            disabled={importing}
          >
            {importing ? "Importing…" : "Import backup"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".awdeck,.zip"
            className="hidden"
            onChange={handleImportChange}
          />
        </div>
      </div>
      {importError && <p className="mt-3 text-sm text-red-500">{importError}</p>}
      {data?.decks?.length ? (
        <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {data.decks.map((deck) => (
            <article
              key={deck.id}
              role="button"
              tabIndex={0}
              aria-label={`Open ${deck.name}`}
              onClick={() => navigate(`/decks/${deck.id}`)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  navigate(`/decks/${deck.id}`);
                }
              }}
              className="group rounded-2xl border border-slate-100 p-4 shadow-sm transition hover:-translate-y-0.5 hover:cursor-pointer hover:border-brand/50 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand dark:border-slate-800 dark:bg-slate-900/60"
            >
              <div className="space-y-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-lg font-semibold text-slate-900 transition group-hover:text-brand dark:text-white">{deck.name}</p>
                    <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                      {deck.target_language || "—"}
                    </p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                    {deck.entry_count ?? 0} entries
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs text-slate-500 dark:text-slate-400">
                  <div className="rounded-xl border border-slate-100 px-3 py-2 dark:border-slate-800">
                    <p className="uppercase text-[0.65rem] text-slate-400 dark:text-slate-500">Cards</p>
                    <p className="text-base font-semibold text-slate-900 dark:text-white">{deck.card_count ?? 0}</p>
                  </div>
                  <div className="rounded-xl border border-slate-100 px-3 py-2 dark:border-slate-800">
                    <p className="uppercase text-[0.65rem] text-slate-400 dark:text-slate-500">Created</p>
                    <p className="text-sm font-semibold text-slate-900 dark:text-white">
                      {deck.created_at ? new Date(deck.created_at).toLocaleString() : "—"}
                    </p>
                  </div>
                  <div className="rounded-xl border border-slate-100 px-3 py-2 dark:border-slate-800">
                    <p className="uppercase text-[0.65rem] text-slate-400 dark:text-slate-500">Updated</p>
                    <p className="text-sm font-semibold text-slate-900 dark:text-white">
                      {deck.last_modified_at ? new Date(deck.last_modified_at).toLocaleString() : "—"}
                    </p>
                  </div>
                </div>
                <DeckQuickActions
                  deckId={deck.id}
                  variant="stacked"
                  className="relative z-10"
                />
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="mt-6 rounded-2xl border border-dashed border-slate-200 p-6 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-300">
          <p>No decks yet. Create one or import a backup to get started.</p>
        </div>
      )}
    </section>
  );
}
