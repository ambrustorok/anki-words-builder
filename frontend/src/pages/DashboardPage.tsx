import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { apiFetch } from "../lib/api";
import { LoadingScreen } from "../components/LoadingScreen";
import { DeckQuickActions } from "../components/DeckQuickActions";

interface DashboardDeck {
  id: string;
  name: string;
  target_language: string;
  card_count: number;
  entry_count: number;
  created_at?: string;
  last_modified_at?: string;
}

interface DashboardEntry {
  id: string;
  deck_name: string;
  target_language: string;
  direction: "forward" | "backward";
  front: string;
  back: string;
  created_at?: string;
  updated_at?: string;
}

interface OverviewResponse {
  requiresOnboarding: boolean;
  staleDecks: DashboardDeck[];
  recentEntries: DashboardEntry[];
}

export function DashboardPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["overview"],
    queryFn: () => apiFetch<OverviewResponse>("/session/overview")
  });

  if (isLoading) {
    return <LoadingScreen label="Loading dashboard" />;
  }

  if (error) {
    return <p className="text-red-500">Failed to load dashboard: {(error as Error).message}</p>;
  }

  return (
    <div className="space-y-8">
      {data?.requiresOnboarding && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-400/40 dark:bg-amber-900/30 dark:text-amber-100">
          Choose your native language to unlock deck creation.{" "}
          <Link className="font-semibold underline" to="/onboarding">
            Complete onboarding
          </Link>
          .
        </div>
      )}

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Least recently updated decks</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">Focus on the decks that need your attention.</p>
          </div>
          {data?.requiresOnboarding ? (
            <Link to="/onboarding" className="rounded-full border border-slate-300 px-4 py-2 text-sm text-slate-600 dark:border-slate-600 dark:text-slate-200">
              Finish onboarding
            </Link>
          ) : (
            <Link to="/decks/new" className="rounded-full bg-brand px-4 py-2 text-sm font-semibold text-slate-900">
              Create deck
            </Link>
          )}
        </div>
        {data?.staleDecks?.length ? (
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            {data.staleDecks.map((deck) => (
              <article key={deck.id} className="rounded-2xl border border-slate-100 p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900/60">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <Link to={`/decks/${deck.id}`} className="text-lg font-semibold text-slate-900 hover:text-brand dark:text-white">
                      {deck.name}
                    </Link>
                    <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                      {deck.target_language || "—"}
                    </p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                    {deck.entry_count ?? 0} entries
                  </span>
                </div>
                <div className="mt-4 grid grid-cols-3 gap-2 text-xs text-slate-500 dark:text-slate-400">
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
                <DeckQuickActions deckId={deck.id} variant="stacked" />
              </article>
            ))}
          </div>
        ) : (
          <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">No decks yet.</p>
        )}
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Last modified entries</h2>
        {data?.recentEntries?.length ? (
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            {data.recentEntries.map((card) => (
              <article key={card.id} className="rounded-2xl border border-slate-100 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-900/60">
                <div className="flex items-center justify-between text-xs uppercase text-slate-500 dark:text-slate-400">
                  <span className="rounded-full bg-white px-2 py-1 text-slate-600 dark:bg-slate-800 dark:text-slate-100">{card.direction}</span>
                  <span>
                    {card.deck_name} · {card.target_language}
                  </span>
                </div>
                <div className="mt-3 space-y-2 text-sm">
                  <div>
                    <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">Front</p>
                    <div
                      className="mt-1 rounded-xl bg-white p-3 text-slate-900 dark:bg-slate-800 dark:text-slate-100"
                      dangerouslySetInnerHTML={{ __html: card.front }}
                    />
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">Back</p>
                    <div
                      className="mt-1 rounded-xl bg-white p-3 text-slate-900 dark:bg-slate-800 dark:text-slate-100"
                      dangerouslySetInnerHTML={{ __html: card.back }}
                    />
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">No cards yet.</p>
        )}
      </section>
    </div>
  );
}
