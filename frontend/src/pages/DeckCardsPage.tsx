import { useState, useEffect, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { apiFetch } from "../lib/api";
import { LoadingScreen } from "../components/LoadingScreen";
import { CardGroupItem } from "../components/CardGroupItem";
import type { CardGroup, DeckTag, TagMode } from "../types";

interface DeckCardsResponse {
    cards: CardGroup[];
    total: number;
    page: number;
    limit: number;
    pages: number;
    deckTags?: DeckTag[];
    tagMode?: TagMode;
    isFiltered?: boolean;
}

export function DeckCardsPage() {
    const { deckId } = useParams();
    const queryClient = useQueryClient();
    const [page, setPage] = useState(1);
    const [searchTerm, setSearchTerm] = useState("");
    const [debouncedSearch, setDebouncedSearch] = useState("");
    const [activeTagNames, setActiveTagNames] = useState<Set<string>>(new Set());
    const [isBulkTagging, setIsBulkTagging] = useState(false);
    const [bulkTagMessage, setBulkTagMessage] = useState("");
    const limit = 20;

    // Debounce search
    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedSearch(searchTerm);
            setPage(1);
        }, 500);
        return () => clearTimeout(timer);
    }, [searchTerm]);

    // Reset page when tag filter changes
    useEffect(() => {
        setPage(1);
    }, [activeTagNames]);

    const { data, isLoading, error, refetch } = useQuery({
        queryKey: ["deck-cards", deckId, page, debouncedSearch, [...activeTagNames].sort().join(",")],
        queryFn: () => {
            const params = new URLSearchParams({
                page: page.toString(),
                limit: limit.toString(),
            });
            if (debouncedSearch) params.set("q", debouncedSearch);
            activeTagNames.forEach((name) => params.append("tags", name));
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

    const toggleTagFilter = (tagName: string) => {
        const tag = (data?.deckTags ?? []).find((t) => t.name === tagName);
        setActiveTagNames((prev) => {
            if (tag?.category_exclusive) {
                // Single-select within this category
                const siblings = new Set(
                    (data?.deckTags ?? [])
                        .filter((t) => t.category === tag.category)
                        .map((t) => t.name)
                );
                const next = new Set([...prev].filter((n) => !siblings.has(n)));
                if (!prev.has(tagName)) next.add(tagName);
                return next;
            }
            const next = new Set(prev);
            if (next.has(tagName)) next.delete(tagName);
            else next.add(tagName);
            return next;
        });
    };

    const handleBulkTag = async () => {
        if (!deckId) return;
        const confirmed = window.confirm(
            "This will use AI to suggest and assign tags to every card in this deck. It may take a while. Continue?"
        );
        if (!confirmed) return;
        setIsBulkTagging(true);
        setBulkTagMessage("");
        try {
            const resp = await apiFetch<{ processed: number; skipped: number }>(
                `/tags/decks/${deckId}/bulk-tag`,
                { method: "POST" }
            );
            setBulkTagMessage(`Done — ${resp.processed} cards tagged, ${resp.skipped} skipped (no tags inferred).`);
            // Refresh card list so tags appear
            queryClient.invalidateQueries({ queryKey: ["deck-cards", deckId] });
        } catch (err) {
            setBulkTagMessage(`Failed: ${(err as Error).message}`);
        } finally {
            setIsBulkTagging(false);
        }
    };

    const deckTags = data?.deckTags ?? [];
    const tagMode = data?.tagMode ?? "off";
    const hasTagFilter = activeTagNames.size > 0;

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

            {/* Search + bulk tag row */}
            <div className="flex flex-wrap gap-3">
                <input
                    type="text"
                    placeholder="Search cards..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    autoFocus
                    className="flex-1 rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm focus:border-brand focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                />
                {tagMode === "auto" && deckTags.length > 0 && (
                    <button
                        onClick={handleBulkTag}
                        disabled={isBulkTagging}
                        className="inline-flex items-center gap-2 rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:border-brand hover:text-brand disabled:opacity-50 dark:border-slate-600 dark:text-slate-200"
                        title="Use AI to assign tags to all cards in this deck"
                    >
                        {isBulkTagging ? (
                            <>
                                <span className="h-3 w-3 animate-spin rounded-full border-2 border-slate-400 border-t-slate-700" />
                                Tagging…
                            </>
                        ) : (
                            "AI tag all cards"
                        )}
                    </button>
                )}
            </div>

            {bulkTagMessage && (
                <p className={`rounded-lg px-4 py-2 text-sm ${bulkTagMessage.startsWith("Failed") ? "bg-red-50 text-red-700 dark:bg-red-500/20 dark:text-red-100" : "bg-emerald-50 text-emerald-700 dark:bg-emerald-400/20 dark:text-emerald-100"}`}>
                    {bulkTagMessage}
                </p>
            )}

            {/* Tag filter chips — only when deck has tags */}
            {tagMode !== "off" && deckTags.length > 0 && (
                <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
                        Filter by tag:
                    </span>
                    {deckTags.map((tag) => {
                        const active = activeTagNames.has(tag.name);
                        return (
                            <button
                                key={tag.id}
                                type="button"
                                onClick={() => toggleTagFilter(tag.name)}
                                className="rounded-full border-2 px-3 py-1 text-xs font-medium transition-all"
                                style={
                                    active
                                        ? { borderColor: tag.color, backgroundColor: tag.color + "33", color: tag.color }
                                        : { borderColor: tag.color + "55", color: tag.color + "99" }
                                }
                            >
                                {tag.name}
                            </button>
                        );
                    })}
                    {hasTagFilter && (
                        <button
                            type="button"
                            onClick={() => setActiveTagNames(new Set())}
                            className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-500 hover:border-slate-500 dark:border-slate-600 dark:text-slate-400"
                        >
                            Clear filter
                        </button>
                    )}
                    {data?.isFiltered && (
                        <span className="text-xs text-slate-400 dark:text-slate-500">
                            {data.total} {data.total === 1 ? "card" : "cards"} match
                        </span>
                    )}
                </div>
            )}

            <div className="grid gap-4 md:grid-cols-2">
                {isLoading && !data ? (
                    <LoadingScreen label="Loading cards" />
                ) : data?.cards.length ? (
                    data.cards.map((group) => (
                        <CardGroupItem key={group.group_id} group={group} onDelete={deleteCard} />
                    ))
                ) : (
                    <p className="rounded-3xl border border-dashed border-slate-200 bg-white px-6 py-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900/70 dark:text-slate-300">
                        {hasTagFilter ? "No cards match the selected tags." : "No cards found."}
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
                        {hasTagFilter && <span className="ml-2 text-xs text-slate-400">(filtered)</span>}
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
