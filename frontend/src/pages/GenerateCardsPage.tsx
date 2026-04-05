import { FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "../lib/api";
import { LoadingScreen } from "../components/LoadingScreen";
import { CandidateCard } from "../components/CandidateCard";
import type {
  DeckTag,
  GenerationCandidate,
  GenerationPreviewResponse,
} from "../types";

// ---------------------------------------------------------------------------
// localStorage persistence helpers
// ---------------------------------------------------------------------------

interface PersistedPrefs {
  cardType: "word" | "sentence";
  selectedByCategory: Record<string, string[]>; // Set serialised as array
  cardsPerCell: number;
  directions: string[];
}

function loadPrefs(deckId: string): Partial<PersistedPrefs> {
  try {
    const raw = localStorage.getItem(`generate-prefs:${deckId}`);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function savePrefs(deckId: string, prefs: PersistedPrefs) {
  try {
    localStorage.setItem(`generate-prefs:${deckId}`, JSON.stringify(prefs));
  } catch {}
}

interface DeckTagsResponse {
  tags: DeckTag[];
  tag_mode: string;
}

interface DeckInfo {
  id: string;
  name: string;
  target_language: string;
}

interface DeckResponse {
  deck: DeckInfo;
}

const MAX_CARDS_PER_CELL = 10;
const MAX_TOTAL = 50;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildCandidates(raw: GenerationPreviewResponse["candidates"]): GenerationCandidate[] {
  return raw.map((c) => ({
    ...c,
    accepted: true,
    editing: false,
    tagIds: [...c.suggested_tag_ids],

    payload: {
      foreign_phrase: c.foreign_phrase,
      native_phrase: c.native_phrase,
      example_sentence: c.example_sentence,
      ...(c.dictionary_entry ? { dictionary_entry: c.dictionary_entry } : {}),
    },
  }));
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function GenerateCardsPage() {
  const { deckId } = useParams<{ deckId: string }>();

  // ---- Deck + tags ----
  const deckQuery = useQuery({
    queryKey: ["deck-info", deckId],
    queryFn: () => apiFetch<DeckResponse>(`/decks/${deckId}`),
    enabled: Boolean(deckId),
  });
  const tagsQuery = useQuery({
    queryKey: ["deck-tags", deckId],
    queryFn: () => apiFetch<DeckTagsResponse>(`/tags/decks/${deckId}/tags`),
    enabled: Boolean(deckId),
  });

  const deck = deckQuery.data?.deck;
  const allTags: DeckTag[] = tagsQuery.data?.tags ?? [];
  const exclusiveCats = allTags.filter((t) => t.category_exclusive);
  const exclusiveCatNames = [...new Set(exclusiveCats.map((t) => t.category))];

  // ---- Form state (seeded from localStorage) ----
  const prefs = deckId ? loadPrefs(deckId) : {};
  const [cardType, setCardType] = useState<"word" | "sentence">(prefs.cardType ?? "word");
  const [description, setDescription] = useState("");
  // {category: Set<tagId>} — restored from serialised arrays
  const [selectedByCategory, setSelectedByCategory] = useState<Record<string, Set<string>>>(
    () => Object.fromEntries(
      Object.entries(prefs.selectedByCategory ?? {}).map(([cat, ids]) => [cat, new Set(ids)])
    )
  );
  const [cardsPerCell, setCardsPerCell] = useState(prefs.cardsPerCell ?? 2);
  const [directions, setDirections] = useState<string[]>(prefs.directions ?? ["forward", "backward"]);

  // Persist prefs whenever they change
  useEffect(() => {
    if (!deckId) return;
    savePrefs(deckId, {
      cardType,
      selectedByCategory: Object.fromEntries(
        Object.entries(selectedByCategory).map(([cat, ids]) => [cat, [...ids]])
      ),
      cardsPerCell,
      directions,
    });
  }, [deckId, cardType, selectedByCategory, cardsPerCell, directions]);

  // ---- Generation state ----
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState("");
  const [steps, setSteps] = useState<string[]>([]);
  const [candidates, setCandidates] = useState<GenerationCandidate[]>([]);

  // ---- Save state ----
  const [saving, setSaving] = useState(false);
  const [saveResult, setSaveResult] = useState<{ saved: number } | null>(null);
  const [saveError, setSaveError] = useState("");

  // Warn on navigation if there are unsaved accepted candidates
  const hasUnsaved = candidates.some((c) => c.accepted) && !saveResult;
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (hasUnsaved) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [hasUnsaved]);

  // ---- Constraint selection ----
  const toggleTagInCategory = (category: string, tagId: string) => {
    setSelectedByCategory((prev) => {
      const next = { ...prev };
      const current = new Set(next[category] ?? []);
      if (current.has(tagId)) current.delete(tagId);
      else current.add(tagId);
      next[category] = current;
      return next;
    });
  };

  const selectAllInCategory = (category: string) => {
    const ids = allTags.filter((t) => t.category === category).map((t) => t.id);
    setSelectedByCategory((prev) => ({ ...prev, [category]: new Set(ids) }));
  };

  const clearCategory = (category: string) => {
    setSelectedByCategory((prev) => ({ ...prev, [category]: new Set() }));
  };

  // ---- Total card count ----
  const constrainedCats = Object.entries(selectedByCategory).filter(
    ([, ids]) => ids.size > 0
  );
  const cellCount = constrainedCats.length === 0
    ? 1
    : constrainedCats.reduce((acc, [, ids]) => acc * ids.size, 1);
  const totalCards = cellCount * cardsPerCell;
  const overLimit = totalCards > MAX_TOTAL;

  // ---- Generate ----
  const handleGenerate = async (e: FormEvent) => {
    e.preventDefault();
    setGenerateError("");
    setSteps([]);
    setCandidates([]);
    setSaveResult(null);
    setSaveError("");
    setGenerating(true);

    try {
      // Build exclusiveConstraints: {categoryName: [tagId, ...]}
      const exclusiveConstraints: Record<string, string[]> = {};
      for (const [cat, ids] of Object.entries(selectedByCategory)) {
        if (ids.size > 0) exclusiveConstraints[cat] = [...ids];
      }

      const resp = await apiFetch<GenerationPreviewResponse>("/generate/preview", {
        method: "POST",
        json: {
          deckId,
          cardType,
          description: description.trim() || null,
          exclusiveConstraints,
          cardsPerCell,
          directions,
        },
      });

      setSteps(resp.steps);
      setCandidates(buildCandidates(resp.candidates));
    } catch (err) {
      setGenerateError((err as Error).message);
    } finally {
      setGenerating(false);
    }
  };

  // ---- Candidate updates ----
  const updateCandidate = (id: string, updates: Partial<GenerationCandidate>) => {
    setCandidates((prev) =>
      prev.map((c) => (c.ephemeral_id === id ? { ...c, ...updates } : c))
    );
  };

  const acceptAll = () => setCandidates((prev) => prev.map((c) => ({ ...c, accepted: true })));
  const rejectAll = () => setCandidates((prev) => prev.map((c) => ({ ...c, accepted: false })));

  const acceptedCount = candidates.filter((c) => c.accepted).length;

  // ---- Save ----
  const handleSave = async () => {
    const toSave = candidates.filter((c) => c.accepted);
    if (!toSave.length) return;
    setSaving(true);
    setSaveError("");
    try {
      const result = await apiFetch<{ saved: number }>("/generate/save", {
        method: "POST",
        json: {
          deckId,
          directions,
          cards: toSave.map((c) => ({
            payload: c.payload,
            tagIds: c.tagIds,
          })),
        },
      });
      setSaveResult(result);
      // Clear saved candidates, keep rejected ones visible
      setCandidates((prev) => prev.filter((c) => !c.accepted));
    } catch (err) {
      setSaveError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setCandidates([]);
    setSaveResult(null);
    setSaveError("");
    setSteps([]);
    setGenerateError("");
  };

  // ---- Loading ----
  if (deckQuery.isLoading || tagsQuery.isLoading) return <LoadingScreen label="Loading deck" />;
  if (!deck) return <p className="text-red-500">Deck not found.</p>;

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link
          to={`/decks/${deckId}`}
          className="text-sm font-semibold text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
        >
          &larr; {deck.name}
        </Link>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-white">
          Generate cards
        </h1>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Input form                                                          */}
      {/* ------------------------------------------------------------------ */}
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <form className="space-y-5" onSubmit={handleGenerate}>
          {/* Card type toggle */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-2">
              Card type
            </p>
            <div className="inline-flex overflow-hidden rounded-full border border-slate-200 text-sm dark:border-slate-700">
              {(["word", "sentence"] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setCardType(t)}
                  className={`px-5 py-2 font-medium capitalize transition ${
                    cardType === t
                      ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900"
                      : "text-slate-500 hover:text-slate-800 dark:text-slate-400"
                  }`}
                >
                  {t === "word" ? "Words / phrases" : "Sentences"}
                </button>
              ))}
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-1.5">
              Topic / description{" "}
              <span className="normal-case font-normal text-slate-400">(optional)</span>
            </label>
            <textarea
              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-white resize-none"
              rows={2}
              maxLength={500}
              placeholder={
                cardType === "sentence"
                  ? "e.g. conversations at the hairdresser, IT workplace phrases…"
                  : "e.g. going to the hairdresser, technology, cooking…"
              }
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          {/* Exclusive category selectors */}
          {exclusiveCatNames.length > 0 && (
            <div className="space-y-4">
              {exclusiveCatNames.map((cat) => {
                const tagsInCat = allTags.filter((t) => t.category === cat);
                const selected = selectedByCategory[cat] ?? new Set<string>();
                const allSelected = tagsInCat.every((t) => selected.has(t.id));
                return (
                  <div key={cat}>
                    <div className="flex items-center gap-3 mb-2">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                        {cat}
                      </p>
                      <button
                        type="button"
                        onClick={() => allSelected ? clearCategory(cat) : selectAllInCategory(cat)}
                        className="text-xs text-brand hover:underline"
                      >
                        {allSelected ? "Clear all" : "Select all"}
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {tagsInCat.map((tag) => {
                        const isSelected = selected.has(tag.id);
                        return (
                          <button
                            key={tag.id}
                            type="button"
                            onClick={() => toggleTagInCategory(cat, tag.id)}
                            className="rounded-full border-2 px-3 py-1.5 text-sm font-medium transition-all min-h-[36px]"
                            style={
                              isSelected
                                ? { borderColor: tag.color, backgroundColor: tag.color + "33", color: tag.color }
                                : { borderColor: tag.color + "55", color: tag.color + "88" }
                            }
                          >
                            {tag.name}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Cards per level + direction + total */}
          <div className="flex flex-wrap items-end gap-5">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-1.5">
                Cards per level
              </label>
              <input
                type="number"
                min={1}
                max={MAX_CARDS_PER_CELL}
                value={cardsPerCell}
                onChange={(e) => setCardsPerCell(Math.min(MAX_CARDS_PER_CELL, Math.max(1, parseInt(e.target.value) || 1)))}
                className="w-20 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-white"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-1.5">
                Directions
              </label>
              <div className="flex gap-3">
                {(["forward", "backward"] as const).map((d) => (
                  <label key={d} className="flex items-center gap-1.5 text-sm text-slate-600 dark:text-slate-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={directions.includes(d)}
                      onChange={(e) =>
                        setDirections((prev) =>
                          e.target.checked ? [...prev, d] : prev.filter((x) => x !== d)
                        )
                      }
                      className="h-4 w-4 rounded border-slate-300"
                    />
                    {d.charAt(0).toUpperCase() + d.slice(1)}
                  </label>
                ))}
              </div>
            </div>
            <div className="ml-auto text-right">
              <p className="text-xs text-slate-400 dark:text-slate-500">Total</p>
              <p className={`text-2xl font-semibold ${overLimit ? "text-red-500" : "text-slate-900 dark:text-white"}`}>
                {totalCards}
              </p>
              {overLimit && (
                <p className="text-xs text-red-500">Max {MAX_TOTAL}</p>
              )}
            </div>
          </div>

          {generateError && (
            <p className="rounded-xl bg-red-50 px-4 py-2.5 text-sm text-red-700 dark:bg-red-500/20 dark:text-red-100">
              {generateError}
            </p>
          )}

          <button
            type="submit"
            disabled={generating || overLimit || directions.length === 0}
            className="rounded-full bg-brand px-6 py-2.5 text-sm font-semibold text-slate-900 disabled:opacity-50 min-h-[44px]"
          >
            {generating ? "Generating…" : `Generate ${totalCards} card${totalCards !== 1 ? "s" : ""}`}
          </button>
        </form>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* Progress steps                                                       */}
      {/* ------------------------------------------------------------------ */}
      {(generating || steps.length > 0) && (
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
          <p className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3">
            {generating ? "Working…" : "Done"}
          </p>
          <ul className="space-y-1.5">
            {steps.map((step, i) => (
              <li key={i} className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                <span className="text-emerald-500">✓</span>
                {step}
              </li>
            ))}
            {generating && (
              <li className="flex items-center gap-2 text-sm text-slate-400 dark:text-slate-500">
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
                In progress…
              </li>
            )}
          </ul>
        </section>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Save result banner                                                   */}
      {/* ------------------------------------------------------------------ */}
      {saveResult && (
        <div className="rounded-2xl bg-emerald-50 px-5 py-4 dark:bg-emerald-400/10">
          <p className="font-semibold text-emerald-800 dark:text-emerald-200">
            {saveResult.saved} card{saveResult.saved !== 1 ? "s" : ""} saved to deck.
          </p>
          <button
            type="button"
            onClick={handleReset}
            className="mt-2 text-sm text-emerald-700 hover:underline dark:text-emerald-300"
          >
            Generate more
          </button>
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Review area                                                          */}
      {/* ------------------------------------------------------------------ */}
      {candidates.length > 0 && (
        <section className="space-y-4">
          {/* Toolbar */}
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
              {candidates.length} candidate{candidates.length !== 1 ? "s" : ""}
            </p>
            <button
              type="button"
              onClick={acceptAll}
              className="rounded-full border border-slate-300 px-3 py-1.5 text-xs text-slate-600 dark:border-slate-600 dark:text-slate-300"
            >
              Accept all
            </button>
            <button
              type="button"
              onClick={rejectAll}
              className="rounded-full border border-slate-300 px-3 py-1.5 text-xs text-slate-600 dark:border-slate-600 dark:text-slate-300"
            >
              Reject all
            </button>
            <div className="ml-auto flex items-center gap-3">
              {saveError && (
                <p className="text-sm text-red-500">{saveError}</p>
              )}
              <button
                type="button"
                onClick={handleSave}
                disabled={saving || acceptedCount === 0}
                className="rounded-full bg-brand px-5 py-2.5 text-sm font-semibold text-slate-900 disabled:opacity-50 min-h-[44px]"
              >
                {saving ? "Saving…" : `Save ${acceptedCount} card${acceptedCount !== 1 ? "s" : ""}`}
              </button>
            </div>
          </div>

          {/* Candidate list */}
          <div className="grid gap-3 md:grid-cols-2">
            {candidates.map((c) => (
              <CandidateCard
                key={c.ephemeral_id}
                candidate={c}
                deckTags={allTags}
                onChange={updateCandidate}
              />
            ))}
          </div>

          {/* Bottom save button for long lists */}
          {candidates.length > 4 && (
            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={handleSave}
                disabled={saving || acceptedCount === 0}
                className="rounded-full bg-brand px-5 py-2.5 text-sm font-semibold text-slate-900 disabled:opacity-50 min-h-[44px]"
              >
                {saving ? "Saving…" : `Save ${acceptedCount} card${acceptedCount !== 1 ? "s" : ""}`}
              </button>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
