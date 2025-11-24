import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "../lib/api";
import { LoadingScreen } from "../components/LoadingScreen";
import type { DeckDetailResponse, DeckField } from "../types";

interface CardGroupResponse {
  deck: DeckDetailResponse["deck"];
  group: {
    id: string;
    payload: Record<string, string>;
    directions: string[];
  };
  audioPreview: string;
  audioPreferences: { voice: string; instructions: string };
}

interface CardOptionsResponse {
  voices: string[];
  defaultAudioInstructions: string;
}

interface Props {
  mode: "create" | "edit";
}

export function CardFormPage({ mode }: Props) {
  const params = useParams();
  const navigate = useNavigate();
  const deckIdParam = params.deckId;
  const groupId = params.groupId;

  const deckId = mode === "create" ? deckIdParam : undefined;

  const deckQuery = useQuery({
    queryKey: ["deck", deckId, "card-form"],
    queryFn: () => apiFetch<DeckDetailResponse>(`/decks/${deckId}`),
    enabled: mode === "create" && Boolean(deckId)
  });

  const groupQuery = useQuery({
    queryKey: ["card-group", groupId],
    queryFn: () => apiFetch<CardGroupResponse>(`/cards/groups/${groupId}`),
    enabled: mode === "edit" && Boolean(groupId)
  });

  const cardOptionsQuery = useQuery({
    queryKey: ["card-options"],
    queryFn: () => apiFetch<CardOptionsResponse>("/cards/options")
  });

  const deck = mode === "create" ? deckQuery.data?.deck : groupQuery.data?.deck;
  const deckIdForSubmit = deck?.id ?? deckIdParam ?? groupQuery.data?.deck.id;

  const [payload, setPayload] = useState<Record<string, string>>({});
  const [directions, setDirections] = useState<string[]>(["forward", "backward"]);
  const [audioPreview, setAudioPreview] = useState("");
  const [audioUrl, setAudioUrl] = useState("");
  const [audioPreferences, setAudioPreferences] = useState({ voice: "random", instructions: "" });
  const [audioEnabled, setAudioEnabled] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [inputMode, setInputMode] = useState<"foreign" | "native">("foreign");
  const [detailsUnlocked, setDetailsUnlocked] = useState(mode === "edit");
  const [isProcessing, setIsProcessing] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (deck) {
      setPayload((prev) => {
        const next: Record<string, string> = {};
        deck.field_schema.forEach((field) => {
          next[field.key] = prev[field.key] ?? "";
        });
        return next;
      });
      setAudioEnabled(Boolean(deck.prompt_templates?.audio?.enabled ?? true));
      if (mode === "create" && cardOptionsQuery.data?.defaultAudioInstructions) {
        setAudioPreferences({
          voice: "random",
          instructions: cardOptionsQuery.data.defaultAudioInstructions.replace("{target_language}", deck.target_language)
        });
      }
    }
  }, [deck, mode, cardOptionsQuery.data?.defaultAudioInstructions]);

  useEffect(() => {
    if (mode === "edit" && groupQuery.data) {
      setPayload(groupQuery.data.group.payload);
      setDirections(groupQuery.data.group.directions);
      setAudioPreview(groupQuery.data.audioPreview);
      setAudioPreferences(groupQuery.data.audioPreferences);
      setAudioEnabled(Boolean(groupQuery.data.deck.prompt_templates?.audio?.enabled ?? true));
      setDetailsUnlocked(true);
      if (groupQuery.data.group.payload.native_phrase && !groupQuery.data.group.payload.foreign_phrase) {
        setInputMode("native");
      }
    }
  }, [groupQuery.data, mode]);

  useEffect(() => {
    if (!audioRef.current || !audioPreview) return;
    try {
      audioRef.current.load();
      void audioRef.current.play();
    } catch (err) {
      // autoplay can fail silently; ignore
    }
  }, [audioPreview]);

  const fieldSchema = deck?.field_schema ?? [];
  const nativeFieldAvailable = fieldSchema.some((field) => field.key === "native_phrase");
  const effectiveInputMode = !nativeFieldAvailable ? "foreign" : inputMode;
  const inputFieldKey = effectiveInputMode === "native" ? "native_phrase" : "foreign_phrase";
  const inputField = fieldSchema.find((field) => field.key === inputFieldKey);
  const activeInputMode = effectiveInputMode;

  const updateField = (field: DeckField, value: string) => {
    setPayload((prev) => ({ ...prev, [field.key]: value }));
  };

  const toggleDirection = (direction: "forward" | "backward") => {
    setDirections((prev) =>
      prev.includes(direction) ? prev.filter((dir) => dir !== direction) : [...prev, direction]
    );
  };

  const runAction = async (action: string) => {
    if (!deckIdForSubmit) return;
    setMessage("");
    setError("");
    const processingAction = action === "populate_all";
    if (processingAction) {
      setIsProcessing(true);
    }
    try {
      const response = await apiFetch<any>("/cards/actions", {
        method: "POST",
        json: {
          deckId: deckIdForSubmit,
          groupId,
          mode,
          action,
          payload,
          directions,
          audioPreview,
          audioUrl,
          audioPreferences,
          inputMode: activeInputMode
        }
      });
      if (response.status === "saved") {
        navigate(`/decks/${response.deckId}`);
        return;
      }
      if (response.payload) {
        setPayload(response.payload);
      }
      if (response.directions) {
        setDirections(response.directions);
      }
      if (typeof response.audioPreview === "string") {
        setAudioPreview(response.audioPreview);
      }
      if (processingAction) {
        setDetailsUnlocked(true);
      }
      setMessage(response.message ?? "Done");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      if (processingAction) {
        setIsProcessing(false);
      }
    }
  };

  if (cardOptionsQuery.isLoading || (mode === "create" && deckQuery.isLoading) || (mode === "edit" && groupQuery.isLoading)) {
    return <LoadingScreen label="Loading card form" />;
  }

  if (cardOptionsQuery.error) {
    return <p className="text-red-500">Failed to load card options.</p>;
  }

  if ((mode === "create" && deckQuery.error) || (mode === "edit" && groupQuery.error)) {
    return <p className="text-red-500">Failed to load card data.</p>;
  }

  if (!deck) {
    return <p className="text-red-500">Deck not found.</p>;
  }

  return (
    <section className="space-y-6">
      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <h1 className="text-xl font-semibold text-slate-900 dark:text-white">{deck.name}</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">Target language: {deck.target_language}</p>
      </div>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-slate-900 dark:text-white">Pick your starting point</p>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Enter whichever phrase you know first, then let the generator fill in the rest.
            </p>
          </div>
          <div className="inline-flex overflow-hidden rounded-full border border-slate-200 dark:border-slate-700">
            <button
              type="button"
              onClick={() => setInputMode("foreign")}
              className={`px-4 py-2 text-sm font-medium transition ${
                activeInputMode === "foreign"
                  ? "bg-brand text-slate-900"
                  : "bg-transparent text-slate-600 dark:text-slate-300"
              }`}
            >
              Foreign phrase
            </button>
            <button
              type="button"
              disabled={!nativeFieldAvailable}
              onClick={() => nativeFieldAvailable && setInputMode("native")}
              className={`px-4 py-2 text-sm font-medium transition ${
                activeInputMode === "native"
                  ? "bg-brand text-slate-900"
                  : "bg-transparent text-slate-600 dark:text-slate-300"
              } ${nativeFieldAvailable ? "" : "opacity-50"}`}
            >
              Native phrase
            </button>
          </div>
        </div>

        <form className="mt-4 space-y-3" onSubmit={(event) => event.preventDefault()}>
          <label className="block text-sm text-slate-700 dark:text-slate-300">
            {inputField?.label ?? (activeInputMode === "native" ? "Native phrase" : "Foreign phrase")}
            <textarea
              className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-base dark:border-slate-700 dark:bg-slate-900"
              rows={3}
              placeholder={inputField?.description}
              value={payload[inputFieldKey] ?? ""}
              onChange={(event) => updateField({ key: inputFieldKey, label: inputField?.label ?? inputFieldKey }, event.target.value)}
            />
          </label>
        </form>

        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => runAction("populate_all")}
            disabled={isProcessing}
            className="inline-flex items-center gap-2 rounded-full bg-brand px-5 py-2 text-sm font-semibold text-slate-900 disabled:opacity-60"
          >
            {isProcessing && <span className="h-3 w-3 animate-spin rounded-full border-2 border-slate-900/30 border-t-slate-900" />}
            Process input
          </button>
        </div>
        <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
          This runs translation + generation and unlocks the remaining fields. You can always tweak them afterward.
        </p>
      </section>

      {detailsUnlocked ? (
        <>
          <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Card details</h2>
              <div className="flex flex-wrap gap-2 text-xs">
                <button className="rounded-full border border-slate-300 px-3 py-1 text-slate-600 dark:border-slate-600 dark:text-slate-200" onClick={() => runAction("regen_native_phrase")}>
                  Regenerate translation
                </button>
                <button className="rounded-full border border-slate-300 px-3 py-1 text-slate-600 dark:border-slate-600 dark:text-slate-200" onClick={() => runAction("regen_dictionary_entry")}>
                  Regenerate dictionary
                </button>
                <button className="rounded-full border border-slate-300 px-3 py-1 text-slate-600 dark:border-slate-600 dark:text-slate-200" onClick={() => runAction("regen_example_sentence")}>
                  Regenerate example
                </button>
              </div>
            </div>
            <div className="mt-4 space-y-4">
              {fieldSchema
                .filter((field) => field.key !== inputFieldKey)
                .map((field) => (
                  <label key={field.key} className="block text-sm text-slate-700 dark:text-slate-300">
                    {field.label}
                    <textarea
                      className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900"
                      rows={field.required ? 3 : 2}
                      value={payload[field.key] ?? ""}
                      onChange={(event) => updateField(field, event.target.value)}
                    />
                  </label>
                ))}
            </div>
          </section>

          {audioEnabled && (
            <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Audio & playback</h2>
              <div className="flex flex-wrap gap-2 text-xs">
                <button className="rounded-full border border-slate-300 px-3 py-1 text-slate-600 dark:border-slate-600 dark:text-slate-200" onClick={() => runAction("regen_audio")}>
                  Regenerate audio
                </button>
                <button className="rounded-full border border-slate-300 px-3 py-1 text-slate-600 dark:border-slate-600 dark:text-slate-200" onClick={() => runAction("fetch_audio")}>
                  Fetch from URL
                </button>
              </div>
            </div>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <label className="text-sm text-slate-700 dark:text-slate-300">
                Voice
                <select
                  className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900"
                  value={audioPreferences.voice}
                  onChange={(event) =>
                    setAudioPreferences((prev) => ({
                      ...prev,
                      voice: event.target.value
                    }))
                  }
                >
                  {cardOptionsQuery.data?.voices.map((voice) => (
                    <option key={voice} value={voice}>
                      {voice}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm text-slate-700 dark:text-slate-300">
                Audio URL
                <input
                  className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900"
                  placeholder="https://example.com/audio.mp3"
                  value={audioUrl}
                  onChange={(event) => setAudioUrl(event.target.value)}
                />
              </label>
            </div>
            <label className="mt-4 block text-sm text-slate-700 dark:text-slate-300">
              Audio instructions
              <textarea
                className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900"
                rows={3}
                value={audioPreferences.instructions}
                onChange={(event) => setAudioPreferences((prev) => ({ ...prev, instructions: event.target.value }))}
              />
            </label>
            {audioPreview && (
              <audio ref={audioRef} autoPlay controls src={`data:audio/mpeg;base64,${audioPreview}`} className="mt-4 w-full rounded-2xl border border-slate-200 dark:border-slate-700" />
            )}
            </section>
          )}
        </>
      ) : (
        <>
          <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Card details</h2>
              <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Populates after processing
              </p>
            </div>
            <div className="mt-4 space-y-4">
              {fieldSchema
                .filter((field) => field.key !== inputFieldKey)
                .map((field) => (
                  <label key={field.key} className="block text-sm text-slate-700 dark:text-slate-300">
                    {field.label}
                    <textarea
                      className={`mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-slate-400 dark:border-slate-700 dark:bg-slate-900/40 ${
                        isProcessing ? "animate-pulse" : ""
                      }`}
                      rows={field.required ? 3 : 2}
                      value=""
                      disabled
                    />
                  </label>
                ))}
            </div>
            <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">
              Process the phrase to unlock and auto-fill these fields.
            </p>
          </section>

          {audioEnabled && (
            <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Audio & playback</h2>
              <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Populates after processing</p>
            </div>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <label className="text-sm text-slate-700 dark:text-slate-300">
                Voice
                <div
                  className={`mt-1 h-10 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-400 dark:border-slate-700 dark:bg-slate-900/40 ${
                    isProcessing ? "animate-pulse" : ""
                  }`}
                >
                  Awaiting generation…
                </div>
              </label>
              <label className="text-sm text-slate-700 dark:text-slate-300">
                Audio URL
                <div
                  className={`mt-1 h-10 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-400 dark:border-slate-700 dark:bg-slate-900/40 ${
                    isProcessing ? "animate-pulse" : ""
                  }`}
                >
                  Awaiting generation…
                </div>
              </label>
            </div>
            <label className="mt-4 block text-sm text-slate-700 dark:text-slate-300">
              Audio instructions
              <div
                className={`mt-1 h-20 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-400 dark:border-slate-700 dark:bg-slate-900/40 ${
                  isProcessing ? "animate-pulse" : ""
                }`}
              >
                Awaiting generation…
              </div>
            </label>
            <div className={`mt-4 h-20 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900/40 ${isProcessing ? "animate-pulse" : ""}`}>
              Audio will appear here after processing.
            </div>
            </section>
          )}
        </>
      )}

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Export directions</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          These decide which cards get exported to Anki. Use forward for Foreign → Native, backward for Native → Foreign.
        </p>
        <div className="mt-4 flex flex-wrap gap-6 text-sm text-slate-700 dark:text-slate-300">
          <label className="inline-flex items-center gap-2">
            <input type="checkbox" checked={directions.includes("forward")} onChange={() => toggleDirection("forward")} />
            Forward (Foreign → Native)
          </label>
          <label className="inline-flex items-center gap-2">
            <input type="checkbox" checked={directions.includes("backward")} onChange={() => toggleDirection("backward")} />
            Backward (Native → Foreign)
          </label>
        </div>
      </section>

      {message && (
        <p className="rounded-lg bg-emerald-50 px-4 py-2 text-sm text-emerald-700 dark:bg-emerald-400/20 dark:text-emerald-100">
          {message}
        </p>
      )}
      {error && (
        <p className="rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700 dark:bg-red-500/20 dark:text-red-100">
          {error}
        </p>
      )}

      <div className="flex flex-wrap gap-3">
        <button className="rounded-full bg-brand px-6 py-3 text-sm font-semibold text-slate-900" onClick={() => runAction("save")}>
          Save card
        </button>
        <button
          type="button"
          className="rounded-full border border-slate-300 px-6 py-3 text-sm text-slate-600 dark:border-slate-600 dark:text-slate-300"
          onClick={() => navigate(`/decks/${deck.id}`)}
        >
          Cancel
        </button>
      </div>
    </section>
  );
}
