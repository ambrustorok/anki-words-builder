import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { apiFetch } from "../lib/api";
import { LoadingScreen } from "../components/LoadingScreen";
import { useSession } from "../lib/session";
import { DeckQuickActions } from "../components/DeckQuickActions";

interface DeckListResponse {
  decks: any[];
}

export function DeckListPage() {
  const session = useSession();
  const { data, isLoading, error } = useQuery({
    queryKey: ["decks"],
    queryFn: () => apiFetch<DeckListResponse>("/decks")
  });

  if (isLoading) {
    return <LoadingScreen label="Loading decks" />;
  }
  if (error) {
    return <p className="text-red-500">Failed to load decks: {(error as Error).message}</p>;
  }

  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900 dark:text-white">Decks</h1>
        {session.data?.needsOnboarding ? (
          <Link to="/onboarding" className="rounded-full border border-slate-300 px-4 py-2 text-sm dark:border-slate-600 dark:text-slate-200">
            Finish onboarding
          </Link>
        ) : (
          <Link to="/decks/new" className="rounded-full bg-brand px-4 py-2 text-sm font-semibold text-slate-900">
            New deck
          </Link>
        )}
      </div>
      <table className="mt-4 w-full text-sm">
        <thead className="text-left text-xs uppercase tracking-wide text-slate-500 dark:text-slate-300">
          <tr>
            <th className="px-3 py-2">Name</th>
            <th className="px-3 py-2">Entries</th>
            <th className="px-3 py-2">Language</th>
            <th className="px-3 py-2">Cards</th>
            <th className="px-3 py-2">Created</th>
            <th className="px-3 py-2">Last updated</th>
            <th className="px-3 py-2 text-right">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {data?.decks?.map((deck) => (
            <tr key={deck.id}>
              <td className="px-3 py-2 font-medium text-brand">
                <Link to={`/decks/${deck.id}`}>{deck.name}</Link>
              </td>
              <td className="px-3 py-2 text-slate-500 dark:text-slate-300">{deck.entry_count ?? 0}</td>
              <td className="px-3 py-2 text-slate-500 dark:text-slate-300">{deck.target_language}</td>
              <td className="px-3 py-2 text-slate-500 dark:text-slate-300">{deck.card_count ?? 0}</td>
              <td className="px-3 py-2 text-slate-500 dark:text-slate-300">
                {deck.created_at ? new Date(deck.created_at).toLocaleDateString() : "—"}
              </td>
              <td className="px-3 py-2 text-slate-500 dark:text-slate-300">
                {deck.last_modified_at ? new Date(deck.last_modified_at).toLocaleDateString() : "—"}
              </td>
              <td className="px-3 py-2 text-right text-xs">
                <DeckQuickActions deckId={deck.id} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
