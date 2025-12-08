import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";

import { apiFetch, API_BASE_URL } from "../lib/api";
import { LoadingScreen } from "../components/LoadingScreen";
import { CardGroupItem } from "../components/CardGroupItem";
import type { DeckDetailResponse } from "../types";

export function DeckDetailPage() {
  const { deckId } = useParams();
  const navigate = useNavigate();
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

  const navigateToCards = () => {
    navigate(`/decks/${deckId}/cards`);
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
          <div className="ml-auto flex flex-wrap gap-2">
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
            <a
              className="rounded-full border border-slate-300 px-4 py-2 text-sm dark:border-slate-600 dark:text-slate-200"
              href={`${API_BASE_URL}/decks/${deck.id}/backup`}
            >
              Backup
            </a>
          </div>
        </div>
        <div className="mt-4 grid gap-4 text-sm text-slate-600 md:grid-cols-3">
          <div
            className="group rounded-2xl border border-slate-100 bg-slate-50 p-4 transition hover:bg-slate-100 dark:border-slate-800 dark:bg-slate-900/60 dark:hover:bg-slate-800 cursor-pointer"
            onClick={navigateToCards}
          >
            <p className="text-xs uppercase text-slate-400 dark:text-slate-500 group-hover:text-brand">Card entries &rarr;</p>
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
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Recent Cards</h2>
          <Link to={`/decks/${deckId}/cards`} className="text-sm font-semibold text-brand hover:underline">
            Manage Cards &rarr;
          </Link>
        </div>
        {data?.cards?.length ? (
          data.cards.map((group) => (
            <CardGroupItem key={group.group_id} group={group} onDelete={deleteCard} />
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
