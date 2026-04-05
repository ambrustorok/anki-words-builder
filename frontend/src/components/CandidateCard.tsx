import { useRef, useState } from "react";
import { GenerationCandidate, DeckTag } from "../types";
import { SafeHtml } from "./SafeHtml";

interface CandidateCardProps {
  candidate: GenerationCandidate;
  deckTags: DeckTag[];
  onChange: (id: string, updates: Partial<GenerationCandidate>) => void;
}

export function CandidateCard({ candidate, deckTags, onChange }: CandidateCardProps) {
  const [expanded, setExpanded] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);

  const audioSrc = candidate.audio_b64
    ? `data:audio/mpeg;base64,${candidate.audio_b64}`
    : null;

  const handlePlayPause = () => {
    if (!audioRef.current) return;
    if (playing) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      setPlaying(false);
    } else {
      audioRef.current.play();
      setPlaying(true);
    }
  };

  const toggle = () =>
    onChange(candidate.ephemeral_id, { accepted: !candidate.accepted });

  const toggleTag = (tagId: string) => {
    const tag = deckTags.find((t) => t.id === tagId);
    const current = new Set(candidate.tagIds);
    if (tag?.category_exclusive) {
      const siblings = new Set(
        deckTags.filter((t) => t.category === tag.category).map((t) => t.id)
      );
      const next = new Set([...current].filter((id) => !siblings.has(id)));
      if (!current.has(tagId)) next.add(tagId);
      onChange(candidate.ephemeral_id, { tagIds: [...next] });
    } else {
      if (current.has(tagId)) current.delete(tagId);
      else current.add(tagId);
      onChange(candidate.ephemeral_id, { tagIds: [...current] });
    }
  };

  const updatePayload = (key: string, value: string) =>
    onChange(candidate.ephemeral_id, {
      payload: { ...candidate.payload, [key]: value },
    });

  const assignedTags = deckTags.filter((t) => candidate.tagIds.includes(t.id));
  const tagsByCategory = deckTags.reduce<Record<string, DeckTag[]>>((acc, t) => {
    const cat = t.category || "Other";
    (acc[cat] = acc[cat] || []).push(t);
    return acc;
  }, {});

  const isDupe = candidate.is_duplicate || candidate.is_possible_duplicate;

  return (
    <article
      className={`rounded-2xl border transition-all ${
        !candidate.accepted
          ? "border-slate-200 bg-slate-50 opacity-50 dark:border-slate-800 dark:bg-slate-900/40"
          : isDupe
          ? "border-amber-300 bg-amber-50 dark:border-amber-500/50 dark:bg-amber-400/10"
          : "border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900/70"
      }`}
    >
      {/* Header row */}
      <div className="flex items-start gap-3 p-4">
        {/* Accept/reject checkbox */}
        <button
          type="button"
          onClick={toggle}
          className={`mt-0.5 h-5 w-5 shrink-0 rounded border-2 transition ${
            candidate.accepted
              ? "border-brand bg-brand"
              : "border-slate-300 bg-white dark:border-slate-600 dark:bg-slate-800"
          }`}
          title={candidate.accepted ? "Reject this card" : "Accept this card"}
        >
          {candidate.accepted && (
            <svg viewBox="0 0 12 12" className="h-full w-full p-0.5 text-slate-900">
              <path
                d="M2 6l3 3 5-5"
                stroke="currentColor"
                strokeWidth="2"
                fill="none"
                strokeLinecap="round"
              />
            </svg>
          )}
        </button>

        {/* Main content */}
        <div className="min-w-0 flex-1">
          {/* Phrase row */}
          <div className="flex flex-wrap items-baseline gap-2">
            <span className="font-semibold text-slate-900 dark:text-white">
              {candidate.payload.foreign_phrase}
            </span>
            <span className="text-slate-400 dark:text-slate-500">→</span>
            <span className="text-slate-600 dark:text-slate-300">
              {candidate.payload.native_phrase}
            </span>
          </div>

          {/* Example sentence */}
          {candidate.payload.example_sentence && (
            <p className="mt-1 text-sm text-slate-500 italic dark:text-slate-400">
              {candidate.payload.example_sentence}
            </p>
          )}

          {/* Duplicate warning */}
          {candidate.is_duplicate && (
            <p className="mt-1 text-xs font-medium text-amber-700 dark:text-amber-400">
              ⚠ Already in deck (exact match)
            </p>
          )}
          {candidate.is_possible_duplicate && !candidate.is_duplicate && (
            <p className="mt-1 text-xs font-medium text-amber-600 dark:text-amber-400">
              ~ Possible duplicate (similar word in deck)
            </p>
          )}

          {/* Tag chips */}
          {assignedTags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {assignedTags.map((tag) => (
                <span
                  key={tag.id}
                  className="rounded-full border px-2 py-0.5 text-xs font-medium"
                  style={{ borderColor: tag.color, color: tag.color, backgroundColor: tag.color + "1a" }}
                >
                  {tag.name}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="flex shrink-0 gap-1.5">
          {/* Audio play button */}
          {audioSrc && (
            <>
              <audio
                ref={audioRef}
                src={audioSrc}
                preload="none"
                onEnded={() => setPlaying(false)}
              />
              <button
                type="button"
                onClick={handlePlayPause}
                title={playing ? "Stop" : "Play pronunciation"}
                className={`flex h-8 w-8 items-center justify-center rounded-lg border transition ${
                  playing
                    ? "border-brand bg-brand/10 text-brand"
                    : "border-slate-200 text-slate-400 hover:border-slate-400 dark:border-slate-700"
                }`}
              >
                {playing ? (
                  // Stop icon
                  <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="currentColor">
                    <rect x="3" y="3" width="10" height="10" rx="1" />
                  </svg>
                ) : (
                  // Play icon
                  <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="currentColor">
                    <path d="M5 3.5l8 4.5-8 4.5V3.5z" />
                  </svg>
                )}
              </button>
            </>
          )}

          {/* Edit toggle */}
          <button
            type="button"
            onClick={() => setExpanded((e) => !e)}
            className="rounded-lg border border-slate-200 px-2.5 py-1 text-xs text-slate-500 hover:border-slate-400 dark:border-slate-700 dark:text-slate-400"
          >
            {expanded ? "Close" : "Edit"}
          </button>
        </div>
      </div>

      {/* Expanded edit panel */}
      {expanded && (
        <div className="border-t border-slate-100 p-4 pt-3 space-y-3 dark:border-slate-800">
          {/* Editable payload fields */}
          {[
            { key: "foreign_phrase", label: "Word / phrase" },
            { key: "native_phrase", label: "Translation" },
            { key: "example_sentence", label: "Example sentence" },
          ].map(({ key, label }) => (
            <div key={key}>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-1">
                {label}
              </label>
              <input
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-white"
                value={candidate.payload[key] ?? ""}
                onChange={(e) => updatePayload(key, e.target.value)}
                spellCheck={false}
              />
            </div>
          ))}

          {/* Dictionary entry */}
          {candidate.payload.dictionary_entry && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-1">
                Dictionary entry
              </p>
              <SafeHtml
                html={candidate.payload.dictionary_entry}
                className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-xs dark:border-slate-800 dark:bg-slate-900/50"
              />
            </div>
          )}

          {/* Tag selector */}
          {deckTags.length > 0 && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-1.5">
                Tags
              </p>
              <div className="space-y-2">
                {Object.entries(tagsByCategory).map(([category, tags]) => (
                  <div key={category}>
                    <p className="text-xs text-slate-400 dark:text-slate-500 mb-1">{category}</p>
                    <div className="flex flex-wrap gap-1.5">
                      {tags.map((tag) => {
                        const selected = candidate.tagIds.includes(tag.id);
                        return (
                          <button
                            key={tag.id}
                            type="button"
                            onClick={() => toggleTag(tag.id)}
                            className="rounded-full border-2 px-2.5 py-0.5 text-xs font-medium transition-all"
                            style={
                              selected
                                ? { borderColor: tag.color, backgroundColor: tag.color + "33", color: tag.color }
                                : { borderColor: tag.color + "55", color: tag.color + "99" }
                            }
                          >
                            {tag.name}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </article>
  );
}
