import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { apiFetch, API_BASE_URL } from "../lib/api";
import { LoadingScreen } from "../components/LoadingScreen";
import type { DeckDetailResponse } from "../types";

export function DeckDetailPage() {
  const { deckId } = useParams();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["deck", deckId],
    queryFn: () => apiFetch<DeckDetailResponse>(`/decks/${deckId}`),
    enabled: Boolean(deckId)
  });

  const deleteCard = async (groupId: string) => {
    const confirmed = window.confirm("Delete this card entry?");
    if (!confirmed) return;
    await apiFetch(`/cards/groups/${groupId}`, { method: "DELETE" });
    refetch();
  };

  if (isLoading || !deckId) {
    return <LoadingScreen label="Loading deck" />;
  }
  if (error) {
    return <p className="text-red-500">Failed to load deck: {(error as Error).message}</p>;
  }
  const deck = data?.deck;
  if (!deck) return null;

  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <div className="flex flex-wrap items-center gap-3">
          <div>
            <p className="text-sm uppercase text-slate-500 dark:text-slate-400">Deck</p>
            <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">{deck.name}</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">Target language: {deck.target_language}</p>
          </div>
          <div className="ml-auto flex gap-2">
            <Link className="rounded-full bg-brand px-4 py-2 text-sm font-semibold text-slate-900" to={`/cards/new/${deck.id}`}>
              Add card
            </Link>
            <Link className="rounded-full border border-slate-300 px-4 py-2 text-sm dark:border-slate-600 dark:text-slate-200" to={`/decks/${deck.id}/edit`}>
              Edit deck
            </Link>
            <a
              className="rounded-full border border-slate-300 px-4 py-2 text-sm dark:border-slate-600 dark:text-slate-200"
              href={`${API_BASE_URL}/decks/${deck.id}/export`}
            >
              Export
            </a>
          </div>
        </div>
        <div className="mt-4 grid gap-4 text-sm text-slate-600 md:grid-cols-3">
          <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-900/60">
            <p className="text-xs uppercase text-slate-400 dark:text-slate-500">Card entries</p>
            <p className="text-2xl font-semibold text-slate-900 dark:text-white">{data?.entryCount ?? 0}</p>
          </div>
          <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-900/60">
            <p className="text-xs uppercase text-slate-400 dark:text-slate-500">Total cards</p>
            <p className="text-2xl font-semibold text-slate-900 dark:text-white">{data?.cardCount ?? 0}</p>
          </div>
          <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-900/60">
            <p className="text-xs uppercase text-slate-400 dark:text-slate-500">Last updated</p>
            <p className="text-lg font-semibold text-slate-900 dark:text-white">
              {data?.lastModified ? new Date(data.lastModified).toLocaleString() : "—"}
            </p>
          </div>
        </div>
      </section>

      <section className="space-y-4">
        {data?.cards?.length ? (
          data.cards.map((group) => (
            <article key={group.group_id} className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
              <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                <span>Created {group.created_at ? new Date(group.created_at).toLocaleString() : "—"}</span>
                <span>Updated {group.updated_at ? new Date(group.updated_at).toLocaleString() : "—"}</span>
                <div className="ml-auto flex gap-3 text-xs">
                  <Link className="text-brand" to={`/cards/${group.group_id}/edit`}>
                    Edit
                  </Link>
                  <button className="text-red-500" onClick={() => deleteCard(group.group_id)}>
                    Delete
                  </button>
                </div>
              </div>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                {group.directions.map((direction) => (
                  <div key={direction.id} className="rounded-2xl border border-slate-100 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-900/60">
                    <p className="text-xs uppercase text-slate-500 dark:text-slate-400">{direction.direction}</p>
                    <div className="mt-2 space-y-2 text-sm">
                      <div>
                        <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">Front</p>
                        <div
                          className="rounded-xl bg-white p-3 dark:bg-slate-800"
                          dangerouslySetInnerHTML={{ __html: direction.front }}
                        />
                      </div>
                      <div>
                        <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">Back</p>
                        <div className="rounded-xl bg-white p-3 dark:bg-slate-800" dangerouslySetInnerHTML={{ __html: direction.back }} />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </article>
          ))
        ) : (
          <p className="rounded-3xl border border-dashed border-slate-200 bg-white px-6 py-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900/70 dark:text-slate-300">
            No cards yet. Start by adding one.
          </p>
        )}
      </section>
    </div>
  );
}
