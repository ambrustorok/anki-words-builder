import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { apiFetch } from "../lib/api";
import { LoadingScreen } from "../components/LoadingScreen";
import { CardGroupItem } from "../components/CardGroupItem";
import { CardGroup } from "../types";

interface DeckCardsResponse {
    cards: CardGroup[];
    total: number;
    page: number;
    limit: number;
    pages: number;
}

export function DeckCardsPage() {
    const { deckId } = useParams();
    const [page, setPage] = useState(1);
    const [searchTerm, setSearchTerm] = useState("");
    const [debouncedSearch, setDebouncedSearch] = useState("");
    const limit = 20;

    // Debounce search
    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedSearch(searchTerm);
            setPage(1);
        }, 500);
        return () => clearTimeout(timer);
    }, [searchTerm]);

    const { data, isLoading, error, refetch } = useQuery({
        queryKey: ["deck-cards", deckId, page, debouncedSearch],
        queryFn: () => {
            const params = new URLSearchParams({
                page: page.toString(),
                limit: limit.toString(),
            });
            if (debouncedSearch) {
                params.set("q", debouncedSearch);
            }
            return apiFetch<DeckCardsResponse>(`/decks/${deckId}/cards?${params.toString()}`);
        },
        enabled: Boolean(deckId),
        keepPreviousData: true,
    });

    const deleteCard = async (groupId: string) => {
        const confirmed = window.confirm("Delete this card entry?");
        if (!confirmed) return;
        await apiFetch(`/cards/groups/${groupId}`, { method: "DELETE" });
        refetch();
    };

    if (error) {
        return <p className="p-6 text-red-500">Failed to load cards: {(error as Error).message}</p>;
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-4">
                <Link to={`/decks/${deckId}`} className="text-sm font-semibold text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white">
                    &larr; Back to Deck
                </Link>
                <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Manage Cards</h1>
            </div>

            <div className="flex gap-4">
                <input
                    type="text"
                    placeholder="Search cards..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    autoFocus
                    className="flex-1 rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm focus:border-brand focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                />
            </div>

            <div className="space-y-4">
                {isLoading && !data ? (
                    <LoadingScreen label="Loading cards" />
                ) : data?.cards.length ? (
                    data.cards.map((group) => (
                        <CardGroupItem key={group.group_id} group={group} onDelete={deleteCard} />
                    ))
                ) : (
                    <p className="rounded-3xl border border-dashed border-slate-200 bg-white px-6 py-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900/70 dark:text-slate-300">
                        No cards found.
                    </p>
                )}
            </div>

            {data && data.pages > 1 && (
                <div className="flex justify-center gap-2">
                    <button
                        disabled={page === 1}
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        className="rounded-lg border border-slate-300 px-4 py-2 text-sm disabled:opacity-50 dark:border-slate-700 dark:text-slate-300"
                    >
                        Previous
                    </button>
                    <span className="flex items-center px-2 text-sm text-slate-600 dark:text-slate-400">
                        Page {page} of {data.pages}
                    </span>
                    <button
                        disabled={page >= data.pages}
                        onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
                        className="rounded-lg border border-slate-300 px-4 py-2 text-sm disabled:opacity-50 dark:border-slate-700 dark:text-slate-300"
                    >
                        Next
                    </button>
                </div>
            )}
        </div>
    );
}
