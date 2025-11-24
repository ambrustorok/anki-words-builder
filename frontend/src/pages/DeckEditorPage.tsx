import { FormEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "../lib/api";
import { LoadingScreen } from "../components/LoadingScreen";
import { FieldSchemaEditor, FieldSchemaEntry, FieldOption } from "../components/FieldSchemaEditor";
import type { DeckDetailResponse, PromptTemplates } from "../types";

const PROMPT_KEYS = ["translation", "dictionary", "sentence"] as const;
type PromptKey = (typeof PROMPT_KEYS)[number];
type PromptValue = { system: string; user: string };
type PromptState = Record<PromptKey, PromptValue>;
type PromptConfig = { system?: string; user?: string };
type PromptLibrary = Record<string, PromptConfig>;

const buildDefaultPrompts = (defaults?: PromptLibrary): PromptState => {
  return PROMPT_KEYS.reduce((acc, key) => {
    const source = defaults?.[key];
    acc[key] = {
      system: source?.system ?? "",
      user: source?.user ?? ""
    };
    return acc;
  }, {} as PromptState);
};

const mergeGenerationPrompts = (base: PromptLibrary | null, visible: PromptState): PromptLibrary => {
  const merged: PromptLibrary = { ...(base ?? {}) };
  PROMPT_KEYS.forEach((key) => {
    merged[key] = {
      ...(merged[key] ?? {}),
      ...visible[key]
    };
  });
  return merged;
};

type FieldSchemaPayloadEntry = Omit<FieldSchemaEntry, "auto_generate"> & { autoGenerate?: boolean };
const serializeFieldSchema = (schema: FieldSchemaEntry[]): FieldSchemaPayloadEntry[] =>
  schema.map(({ auto_generate, ...rest }) => ({
    ...rest,
    autoGenerate: auto_generate
  }));

const CARD_DIRECTIONS = ["forward", "backward"] as const;
type CardDirectionKey = (typeof CARD_DIRECTIONS)[number];

interface CardTemplateFace {
  front: string;
  back: string;
}

type CardTemplateState = Record<CardDirectionKey, CardTemplateFace>;
type CardTemplateInput = Partial<Record<CardDirectionKey, Partial<CardTemplateFace>>>;

const createEmptyCardTemplates = (): CardTemplateState => ({
  forward: { front: "", back: "" },
  backward: { front: "", back: "" }
});

const buildCardTemplateState = (
  source?: CardTemplateInput | null,
  base?: CardTemplateState | null
): CardTemplateState => {
  const seed: CardTemplateState = base
    ? {
        forward: { ...base.forward },
        backward: { ...base.backward }
      }
    : createEmptyCardTemplates();
  CARD_DIRECTIONS.forEach((direction) => {
    const override = source?.[direction];
    if (!override) return;
    if (override.front !== undefined) {
      seed[direction].front = override.front ?? "";
    }
    if (override.back !== undefined) {
      seed[direction].back = override.back ?? "";
    }
  });
  return seed;
};

const cloneCardTemplates = (state: CardTemplateState): CardTemplateState => ({
  forward: { ...state.forward },
  backward: { ...state.backward }
});

interface DeckOptionsResponse {
  fieldLibrary: FieldOption[];
  defaultFieldSchema: FieldSchemaEntry[];
  targetLanguageOptions: string[];
  audioInstructionsTemplate: string;
  defaultCardTemplates: CardTemplateInput;
  defaultGenerationPrompts: PromptLibrary;
}

interface Props {
  mode: "create" | "edit";
}

export function DeckEditorPage({ mode }: Props) {
  const { deckId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [targetLanguage, setTargetLanguage] = useState("");
  const [fieldSchema, setFieldSchema] = useState<FieldSchemaEntry[]>([]);
  const [audioInstructions, setAudioInstructions] = useState("");
  const [audioEnabled, setAudioEnabled] = useState(true);
  const [prompts, setPrompts] = useState<PromptState>(() => buildDefaultPrompts());
  const [fullGenerationPrompts, setFullGenerationPrompts] = useState<PromptLibrary | null>(null);
  const [cardTemplates, setCardTemplates] = useState<CardTemplateState>(() => createEmptyCardTemplates());
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(false);
  const loadedDeckIdRef = useRef<string | null>(null);
  const audioTemplateRef = useRef("");
  const cardTemplateDefaultsRef = useRef<CardTemplateState>(createEmptyCardTemplates());
  const isEdit = mode === "edit";

  const { data: options, isLoading: optionsLoading } = useQuery({
    queryKey: ["deck-options"],
    queryFn: () => apiFetch<DeckOptionsResponse>("/decks/options")
  });

  const { data: deckData, isLoading: deckLoading } = useQuery({
    queryKey: ["deck", deckId, "edit"],
    queryFn: () => apiFetch<DeckDetailResponse>(`/decks/${deckId}`),
    enabled: mode === "edit" && Boolean(deckId)
  });

  useEffect(() => {
    audioTemplateRef.current = options?.audioInstructionsTemplate ?? "";
  }, [options]);

  useEffect(() => {
    if (options?.defaultCardTemplates) {
      cardTemplateDefaultsRef.current = buildCardTemplateState(options.defaultCardTemplates, null);
    }
  }, [options]);

  useEffect(() => {
    if (options && mode === "create") {
      const defaults = buildDefaultPrompts(options.defaultGenerationPrompts);
      setFieldSchema(options.defaultFieldSchema);
      setAudioInstructions(options.audioInstructionsTemplate);
      setTargetLanguage(options.targetLanguageOptions[0] ?? "");
      setPrompts(defaults);
      setFullGenerationPrompts({ ...(options.defaultGenerationPrompts ?? {}) });
      setCardTemplates(cloneCardTemplates(cardTemplateDefaultsRef.current));
      loadedDeckIdRef.current = null;
    }
  }, [options, mode]);

  useEffect(() => {
    if (mode === "edit" && deckData) {
      const deckIdentifier = deckData.deck.id;
      if (loadedDeckIdRef.current === deckIdentifier) {
        return;
      }
      loadedDeckIdRef.current = deckIdentifier;
      setName(deckData.deck.name);
      setTargetLanguage(deckData.deck.target_language);
      setFieldSchema(deckData.deck.field_schema);
      const audioTemplate =
        (deckData.deck.prompt_templates?.audio as { instructions?: string })?.instructions ?? audioTemplateRef.current;
      setAudioInstructions(audioTemplate);
      setAudioEnabled(Boolean((deckData.deck.prompt_templates?.audio as { enabled?: boolean })?.enabled ?? true));
      const generationPrompts = (deckData.generationPrompts ?? {}) as PromptLibrary;
      setFullGenerationPrompts({ ...generationPrompts });
      const merged = buildDefaultPrompts(generationPrompts);
      setPrompts(merged);
      const promptTemplates = (deckData.deck.prompt_templates ?? {}) as PromptTemplates;
      const mergedCardTemplates = buildCardTemplateState(
        {
          forward: promptTemplates.forward,
          backward: promptTemplates.backward
        },
        cardTemplateDefaultsRef.current
      );
      setCardTemplates(mergedCardTemplates);
    }
  }, [deckData, mode]);

  if (optionsLoading || (mode === "edit" && deckLoading)) {
    return <LoadingScreen label="Loading deck editor" />;
  }

  const handleCardTemplateChange = (direction: CardDirectionKey, face: keyof CardTemplateFace, value: string) => {
    setCardTemplates((prev) => ({
      ...prev,
      [direction]: {
        ...prev[direction],
        [face]: value
      }
    }));
  };

  const handlePromptChange = (key: PromptKey, field: keyof PromptValue, value: string) => {
    setPrompts((prev) => ({
      ...prev,
      [key]: {
        ...prev[key],
        [field]: value
      }
    }));
    setFullGenerationPrompts((prev) => ({
      ...(prev ?? {}),
      [key]: {
        ...((prev ?? {})[key] ?? {}),
        [field]: value
      }
    }));
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      const generationPromptsPayload = mergeGenerationPrompts(fullGenerationPrompts, prompts);
      const payload = {
        name,
        targetLanguage,
        fieldSchema: serializeFieldSchema(fieldSchema),
        audioInstructions,
        audioEnabled,
        generationPrompts: generationPromptsPayload,
        cardTemplates: cardTemplates
      };
      if (mode === "create") {
        const response = await apiFetch<{ deck: { id: string } }>("/decks", {
          method: "POST",
          json: payload
        });
        await queryClient.invalidateQueries({ queryKey: ["decks"] });
        await queryClient.invalidateQueries({ queryKey: ["overview"] });
        navigate(`/decks/${response.deck.id}`);
      } else if (deckId) {
        await apiFetch(`/decks/${deckId}`, { method: "PUT", json: payload });
        await queryClient.invalidateQueries({ queryKey: ["deck", deckId] });
        await queryClient.invalidateQueries({ queryKey: ["decks"] });
        await queryClient.invalidateQueries({ queryKey: ["overview"] });
        window.scrollTo({ top: 0, behavior: "smooth" });
        navigate(`/decks/${deckId}`);
      }
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handleDelete = async () => {
    if (mode !== "edit" || !deckId) return;
    const confirmed = window.confirm("Delete this deck and all of its cards?");
    if (!confirmed) return;
    setDeleting(true);
    try {
      await apiFetch(`/decks/${deckId}`, { method: "DELETE" });
      navigate("/decks");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <form className="space-y-6" onSubmit={handleSubmit}>
      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-slate-900 dark:text-white">
              {mode === "create" ? "Create deck" : "Edit deck"}
            </h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Adjust the basics, schema, prompts, and audio defaults for this deck.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="submit"
              className="rounded-full bg-brand px-6 py-2 text-sm font-semibold text-slate-900"
            >
              {mode === "create" ? "Create deck" : "Save changes"}
            </button>
            <button
              type="button"
              className="rounded-full border border-slate-300 px-6 py-2 text-sm dark:border-slate-600 dark:text-slate-200"
              onClick={() => navigate(mode === "create" ? "/decks" : `/decks/${deckId}`)}
            >
              Cancel
            </button>
          </div>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="text-sm text-slate-700 dark:text-slate-300">
            Name
            <input
              className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
            />
          </label>
          <label className="text-sm text-slate-700 dark:text-slate-300">
            Target language
            <select
              className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900"
              value={targetLanguage}
              onChange={(event) => setTargetLanguage(event.target.value)}
              required
            >
              <option value="">Select a language</option>
              {options?.targetLanguageOptions.map((language) => (
                <option key={language} value={language}>
                  {language}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Field schema</h2>
        {options && (
          <FieldSchemaEditor options={options.fieldLibrary} schema={fieldSchema} onChange={setFieldSchema} />
        )}
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Card templates</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Control how the front/back of each card direction should render. Use placeholders like{" "}
              <code className="rounded bg-slate-100 px-1 text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                &#123;&#123;foreign_phrase&#125;&#125;
              </code>{" "}
              anywhere in the markup.
            </p>
          </div>
          <Link to="/help" className="text-sm font-semibold text-brand">
            View variable guide →
          </Link>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {CARD_DIRECTIONS.map((direction) => (
            <div key={direction} className="rounded-2xl border border-slate-100 p-4 dark:border-slate-800 dark:bg-slate-900/60">
              <p className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-300">
                {direction === "forward" ? "Forward card" : "Backward card"}
              </p>
              <label className="mt-3 block text-xs font-semibold uppercase text-slate-400 dark:text-slate-500">
                Front template
              </label>
              <textarea
                className="mt-1 h-28 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-white"
                value={cardTemplates[direction].front}
                onChange={(event) => handleCardTemplateChange(direction, "front", event.target.value)}
              />
              <label className="mt-3 block text-xs font-semibold uppercase text-slate-400 dark:text-slate-500">
                Back template
              </label>
              <textarea
                className="mt-1 h-28 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-white"
                value={cardTemplates[direction].back}
                onChange={(event) => handleCardTemplateChange(direction, "back", event.target.value)}
              />
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Audio settings</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Toggle audio generation and fine-tune the default instructions.
            </p>
          </div>
          <label className="inline-flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
            <input
              type="checkbox"
              checked={audioEnabled}
              onChange={(event) => setAudioEnabled(event.target.checked)}
            />
            Enable audio generation
          </label>
        </div>
        <label className="mt-4 block text-sm text-slate-700 dark:text-slate-300">
          Audio instructions
          <textarea
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
            rows={3}
            value={audioInstructions}
            onChange={(event) => setAudioInstructions(event.target.value)}
            disabled={!audioEnabled}
          />
        </label>
        {!audioEnabled && (
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            Re-enable audio to edit the default instructions.
          </p>
        )}
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Generation prompts</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          {PROMPT_KEYS.map((key) => (
            <div key={key} className="rounded-2xl border border-slate-100 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-900/60">
              <p className="text-sm font-semibold text-slate-900 capitalize dark:text-white">{key}</p>
              <textarea
                className="mt-2 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
                rows={3}
                placeholder="System prompt"
                value={prompts[key].system}
                onChange={(event) => handlePromptChange(key, "system", event.target.value)}
              />
              <textarea
                className="mt-2 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
                rows={4}
                placeholder="User prompt"
                value={prompts[key].user}
                onChange={(event) => handlePromptChange(key, "user", event.target.value)}
              />
            </div>
          ))}
        </div>
      </section>

      {error && <p className="text-sm text-red-500">{error}</p>}

      {isEdit && deckId && (
        <section className="rounded-3xl border border-red-200 bg-red-50 p-6 shadow-sm dark:border-red-400/40 dark:bg-red-500/10">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-red-700 dark:text-red-200">Danger zone</h2>
              <p className="text-sm text-red-600 dark:text-red-100">
                This permanently removes the deck and every card inside it.
              </p>
            </div>
            <button
              type="button"
              onClick={handleDelete}
              disabled={deleting}
              className="rounded-full border border-red-500 px-6 py-3 text-sm font-semibold text-red-600 disabled:opacity-60 dark:border-red-300 dark:text-red-100"
            >
              {deleting ? "Deleting…" : "Delete deck"}
            </button>
          </div>
        </section>
      )}
    </form>
  );
}
