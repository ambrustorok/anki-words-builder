import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "../lib/api";
import { LoadingScreen } from "../components/LoadingScreen";
import type { DeckDetailResponse, DeckField, DeckTag, TagMode } from "../types";

interface CardGroupResponse {
  deck: DeckDetailResponse["deck"];
  group: {
    id: string;
    payload: Record<string, string>;
    directions: string[];
    tags?: DeckTag[];
  };
  audioPreview: string;
  audioPreferences: { voice: string; instructions: string };
  deckTags?: DeckTag[];
  tagMode?: TagMode;
}

interface CardOptionsResponse {
  voices: string[];
  defaultAudioInstructions: string;
}

interface CardActionResponse {
  status?: "ok" | "saved";
  message?: string;
  deckId?: string;
  cardGroupId?: string;
  payload?: Record<string, string>;
  directions?: string[];
  audioPreview?: string;
  suggestedTagNames?: string[];
}

interface Props {
  mode: "create" | "edit";
}

const LOCAL_PHRASES_KEY = "awb-card-start-phrases";
const LOCAL_INPUT_MODE_KEY = "awb-card-input-mode";
const LOCAL_AUDIO_VOICE_KEY = "awb-card-audio-voice";

type PhraseKey = "foreign_phrase" | "native_phrase";
type StoredPhrases = Partial<Record<PhraseKey, string>>;

function getStoredPhrases(): StoredPhrases {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(LOCAL_PHRASES_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object") {
      return parsed as StoredPhrases;
    }
  } catch {
    // ignore JSON issues
  }
  return {};
}

function persistStoredPhrases(updates: StoredPhrases) {
  if (typeof window === "undefined") return;
  const next = { ...getStoredPhrases(), ...updates };
  try {
    window.localStorage.setItem(LOCAL_PHRASES_KEY, JSON.stringify(next));
  } catch {
    // ignore storage quota issues
  }
}

function clearStoredPhrases() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(LOCAL_PHRASES_KEY);
}

function getStoredVoice(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(LOCAL_AUDIO_VOICE_KEY);
}

function persistStoredVoice(voice: string) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(LOCAL_AUDIO_VOICE_KEY, voice);
  } catch {
    // ignore
  }
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

  const [payload, setPayload] = useState<Record<string, string>>(() => (mode === "create" ? { ...getStoredPhrases() } : {}));
  const [directions, setDirections] = useState<string[]>(["forward", "backward"]);
  const [audioPreview, setAudioPreview] = useState("");
  const [audioUrl, setAudioUrl] = useState("");
  const initialVoice = mode === "create" ? getStoredVoice() ?? "random" : "random";
  const [audioPreferences, setAudioPreferences] = useState({ voice: initialVoice, instructions: "" });
  const [audioEnabled, setAudioEnabled] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [inputMode, setInputMode] = useState<"foreign" | "native">(() => {
    if (mode === "edit") return "foreign";
    if (typeof window === "undefined") return "foreign";
    const stored = window.localStorage.getItem(LOCAL_INPUT_MODE_KEY);
    return stored === "native" ? "native" : "foreign";
  });
  const [detailsUnlocked, setDetailsUnlocked] = useState(mode === "edit");
  const [isProcessing, setIsProcessing] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Tag state
  const [deckTags, setDeckTags] = useState<DeckTag[]>([]);
  const [tagMode, setTagMode] = useState<TagMode>("off");
  const [selectedTagIds, setSelectedTagIds] = useState<Set<string>>(new Set());
  const [suggestedTagNames, setSuggestedTagNames] = useState<string[]>([]);
  const [isSuggestingTags, setIsSuggestingTags] = useState(false);

  useEffect(() => {
    if (deck) {
      setPayload((prev) => {
        const next: Record<string, string> = {};
        deck.field_schema.forEach((field) => {
          next[field.key] = prev[field.key] ?? "";
        });
        if (mode === "create") {
          persistStoredPhrases({
            foreign_phrase: next.foreign_phrase ?? "",
            native_phrase: next.native_phrase ?? ""
          });
        }
        return next;
      });
      setAudioEnabled(Boolean(deck.prompt_templates?.audio?.enabled ?? true));
      if (mode === "create" && cardOptionsQuery.data?.defaultAudioInstructions) {
        setAudioPreferences((prev) => ({
          voice: prev.voice || getStoredVoice() || "random",
          instructions: cardOptionsQuery.data.defaultAudioInstructions.replace("{target_language}", deck.target_language)
        }));
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
      // Load tags
      if (groupQuery.data.deckTags) setDeckTags(groupQuery.data.deckTags);
      if (groupQuery.data.tagMode) setTagMode(groupQuery.data.tagMode);
      if (groupQuery.data.group.tags) {
        setSelectedTagIds(new Set(groupQuery.data.group.tags.map((t) => t.id)));
      }
    }
  }, [groupQuery.data, mode]);

  useEffect(() => {
    if (mode === "create" && deck) {
      // Fetch deck tags for create mode
      apiFetch<{ tags: DeckTag[]; tag_mode: TagMode }>(`/tags/decks/${deck.id}/tags`).then((resp) => {
        setDeckTags(resp.tags);
        setTagMode(resp.tag_mode || "off");
      }).catch(() => {});
    }
  }, [deck?.id, mode]);

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
  const effectiveInputMode = mode === "edit" ? "foreign" : !nativeFieldAvailable ? "foreign" : inputMode;
  const inputFieldKey = effectiveInputMode === "native" ? "native_phrase" : "foreign_phrase";
  const inputField = fieldSchema.find((field) => field.key === inputFieldKey);
  const activeInputMode = effectiveInputMode;

  const updateField = (field: DeckField, value: string) => {
    setPayload((prev) => {
      const next = { ...prev, [field.key]: value };
      if (
        mode === "create" &&
        (field.key === "foreign_phrase" || field.key === "native_phrase")
      ) {
        const phraseKey = field.key as PhraseKey;
        persistStoredPhrases({ [phraseKey]: value });
      }
      return next;
    });
  };

  const toggleDirection = (direction: "forward" | "backward") => {
    setDirections((prev) =>
      prev.includes(direction) ? prev.filter((dir) => dir !== direction) : [...prev, direction]
    );
  };

  const changeInputMode = (nextMode: "foreign" | "native") => {
    setInputMode(nextMode);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(LOCAL_INPUT_MODE_KEY, nextMode);
    }
  };

  const updateVoicePreference = (voice: string) => {
    setAudioPreferences((prev) => ({ ...prev, voice }));
    persistStoredVoice(voice);
  };

  const toggleTag = (tagId: string) => {
    const tag = deckTags.find((t) => t.id === tagId);
    setSelectedTagIds((prev) => {
      if (tag?.category_exclusive) {
        // Single-select within this category: deselect all siblings, select this one
        // (unless it was already selected — then deselect it)
        const siblingIds = new Set(
          deckTags.filter((t) => t.category === tag.category).map((t) => t.id)
        );
        const next = new Set([...prev].filter((id) => !siblingIds.has(id)));
        if (!prev.has(tagId)) next.add(tagId);
        return next;
      }
      const next = new Set(prev);
      if (next.has(tagId)) next.delete(tagId);
      else next.add(tagId);
      return next;
    });
    // Remove from AI suggestions once explicitly toggled
    setSuggestedTagNames((prev) => {
      if (!tag) return prev;
      return prev.filter((n) => n !== tag.name);
    });
  };

  const acceptSuggestedTag = (tagName: string) => {
    const tag = deckTags.find((t) => t.name === tagName);
    if (tag) {
      setSelectedTagIds((prev) => {
        if (tag.category_exclusive) {
          const siblingIds = new Set(
            deckTags.filter((t) => t.category === tag.category).map((t) => t.id)
          );
          const next = new Set([...prev].filter((id) => !siblingIds.has(id)));
          next.add(tag.id);
          return next;
        }
        return new Set([...prev, tag.id]);
      });
    }
    setSuggestedTagNames((prev) => prev.filter((n) => n !== tagName));
  };

  const dismissSuggestedTag = (tagName: string) => {
    setSuggestedTagNames((prev) => prev.filter((n) => n !== tagName));
  };

  const runSuggestTags = async () => {
    if (!deckIdForSubmit) return;
    setIsSuggestingTags(true);
    try {
      const response = await apiFetch<CardActionResponse>("/cards/actions", {
        method: "POST",
        json: {
          deckId: deckIdForSubmit,
          groupId,
          mode,
          action: "suggest_tags",
          payload,
          directions,
          audioPreview,
          audioUrl,
          audioPreferences,
          inputMode: activeInputMode,
          tagIds: [...selectedTagIds],
        }
      });
      if (response.suggestedTagNames) {
        // Only show suggestions for tags not already selected
        const newSuggestions = (response.suggestedTagNames as string[]).filter(
          (name) => !selectedTagIds.has(deckTags.find((t) => t.name === name)?.id ?? "")
        );
        setSuggestedTagNames(newSuggestions);
        if (newSuggestions.length === 0) setMessage("No new tag suggestions.");
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsSuggestingTags(false);
    }
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
      const response = await apiFetch<CardActionResponse>("/cards/actions", {
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
          inputMode: activeInputMode,
          tagIds: [...selectedTagIds],
        }
      });
      if (response.status === "saved") {
        if (mode === "create") {
          clearStoredPhrases();
        }
        navigate(`/decks/${response.deckId}`);
        return;
      }
      if (response.payload) {
        setPayload(response.payload);
        if (mode === "create") {
          persistStoredPhrases({
            foreign_phrase: response.payload.foreign_phrase ?? "",
            native_phrase: response.payload.native_phrase ?? ""
          });
        }
      }
      if (response.directions) {
        setDirections(response.directions);
      }
      if (typeof response.audioPreview === "string") {
        setAudioPreview(response.audioPreview);
      }
      if (processingAction) {
        setDetailsUnlocked(true);
        // AI auto mode: show suggested tags from populate_all response
        if (response.suggestedTagNames && tagMode === "auto") {
          const newSuggestions = (response.suggestedTagNames as string[]).filter(
            (name) => !selectedTagIds.has(deckTags.find((t) => t.name === name)?.id ?? "")
          );
          setSuggestedTagNames(newSuggestions);
        }
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
    <section className="mx-auto max-w-4xl space-y-6">
      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-slate-900 dark:text-white">
              {mode === "create" ? `Add card · ${deck.name}` : `Edit card · ${deck.name}`}
            </h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">Target language: {deck.target_language}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button className="rounded-full bg-brand px-6 py-2 text-sm font-semibold text-slate-900" onClick={() => runAction("save")}>
              {mode === "create" ? "Save card" : "Save changes"}
            </button>
            <button
              type="button"
              className="rounded-full border border-slate-300 px-6 py-2 text-sm text-slate-600 dark:border-slate-600 dark:text-slate-300"
              onClick={() => navigate(`/decks/${deck.id}`)}
            >
              Cancel
            </button>
          </div>
        </div>
      </div>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-slate-900 dark:text-white">
              {mode === "edit" ? "Edit phrase" : "Pick your starting point"}
            </p>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {mode === "edit"
                ? "Update the primary phrase before regenerating translations."
                : "Enter whichever phrase you know first, then let the generator fill the rest."}
            </p>
          </div>
          {mode === "create" && (
            <div className="inline-flex overflow-hidden rounded-full border border-slate-200 dark:border-slate-700">
              <button
                type="button"
                onClick={() => changeInputMode("foreign")}
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
                onClick={() => nativeFieldAvailable && changeInputMode("native")}
                className={`px-4 py-2 text-sm font-medium transition ${
                  activeInputMode === "native"
                    ? "bg-brand text-slate-900"
                    : "bg-transparent text-slate-600 dark:text-slate-300"
                } ${nativeFieldAvailable ? "" : "opacity-50"}`}
              >
                Native phrase
              </button>
            </div>
          )}
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

        {mode === "create" && (
          <>
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
          </>
        )}
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
                  onChange={(event) => updateVoicePreference(event.target.value)}
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
                  <select
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900"
                    value={audioPreferences.voice}
                    onChange={(event) => updateVoicePreference(event.target.value)}
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
              <div className="mt-4 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900/40">
                Generate or upload audio to preview it here. Voice + instructions are already saved for the next run.
              </div>
            </section>
          )}
        </>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Tags section — only shown when tagMode is not 'off'                */}
      {/* ------------------------------------------------------------------ */}
      {tagMode !== "off" && deckTags.length > 0 && (
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Tags</h2>
            {tagMode === "auto" && (
              <button
                type="button"
                onClick={runSuggestTags}
                disabled={isSuggestingTags}
                className="inline-flex items-center gap-2 rounded-full border border-slate-300 px-4 py-1.5 text-sm text-slate-600 disabled:opacity-50 dark:border-slate-600 dark:text-slate-300"
              >
                {isSuggestingTags && (
                  <span className="h-3 w-3 animate-spin rounded-full border-2 border-slate-400 border-t-slate-700" />
                )}
                Suggest tags
              </button>
            )}
          </div>

          {/* AI suggestion chips (dashed outline, not yet accepted) */}
          {suggestedTagNames.length > 0 && (
            <div className="mt-3">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
                AI suggestions — click to accept
              </p>
              <div className="flex flex-wrap gap-2">
                {suggestedTagNames.map((name) => {
                  const tag = deckTags.find((t) => t.name === name);
                  const color = tag?.color ?? "#6366f1";
                  return (
                    <div key={name} className="flex items-center gap-0.5">
                      <button
                        type="button"
                        onClick={() => acceptSuggestedTag(name)}
                        className="rounded-full border-2 border-dashed px-3 py-1 text-sm font-medium transition-all hover:opacity-100"
                        style={{ borderColor: color, color, opacity: 0.75 }}
                        title="Click to accept this suggestion"
                      >
                        {name}
                      </button>
                      <button
                        type="button"
                        onClick={() => dismissSuggestedTag(name)}
                        className="text-slate-400 hover:text-red-500 text-base leading-none"
                        title="Dismiss"
                      >
                        ×
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Selected / available tags grouped by category */}
          {(() => {
            const byCategory = deckTags.reduce<Record<string, DeckTag[]>>((acc, tag) => {
              const cat = tag.category || "Uncategorized";
              (acc[cat] = acc[cat] || []).push(tag);
              return acc;
            }, {});
            return (
              <div className="mt-4 space-y-3">
                {Object.entries(byCategory).map(([category, tags]) => (
                  <div key={category}>
                    <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
                      {category}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {tags.map((tag) => {
                        const isSelected = selectedTagIds.has(tag.id);
                        return (
                          <button
                            key={tag.id}
                            type="button"
                            onClick={() => toggleTag(tag.id)}
                            className="rounded-full border-2 px-3 py-1 text-sm font-medium transition-all"
                            style={
                              isSelected
                                ? { borderColor: tag.color, backgroundColor: tag.color + "33", color: tag.color }
                                : { borderColor: tag.color + "66", color: tag.color + "99" }
                            }
                            title={isSelected ? "Remove tag" : "Add tag"}
                          >
                            {tag.name}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            );
          })()}
        </section>
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

    </section>
  );
}
