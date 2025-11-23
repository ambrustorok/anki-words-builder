import { FormEvent, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "../lib/api";
import { LoadingScreen } from "../components/LoadingScreen";
import { FieldSchemaEditor, FieldSchemaEntry, FieldOption } from "../components/FieldSchemaEditor";
import type { DeckDetailResponse } from "../types";

const PROMPT_KEYS = ["translation", "dictionary", "sentence"] as const;
type PromptKey = (typeof PROMPT_KEYS)[number];
type PromptValue = { system: string; user: string };
type PromptState = Record<PromptKey, PromptValue>;
type PromptConfig = { system?: string; user?: string };
type PromptLibrary = Record<string, PromptConfig>;

interface DeckOptionsResponse {
  fieldLibrary: FieldOption[];
  defaultFieldSchema: FieldSchemaEntry[];
  targetLanguageOptions: string[];
  audioInstructionsTemplate: string;
  defaultGenerationPrompts: PromptLibrary;
}

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

const promptsEqual = (a?: PromptState | null, b?: PromptState | null) => {
  if (!a || !b) return false;
  return PROMPT_KEYS.every((key) => a[key].system === b[key].system && a[key].user === b[key].user);
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

interface Props {
  mode: "create" | "edit";
}

export function DeckEditorPage({ mode }: Props) {
  const { deckId } = useParams();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [targetLanguage, setTargetLanguage] = useState("");
  const [fieldSchema, setFieldSchema] = useState<FieldSchemaEntry[]>([]);
  const [audioInstructions, setAudioInstructions] = useState("");
  const [audioEnabled, setAudioEnabled] = useState(true);
  const [prompts, setPrompts] = useState<PromptState>(() => buildDefaultPrompts());
  const [initialPrompts, setInitialPrompts] = useState<PromptState | null>(null);
  const [fullGenerationPrompts, setFullGenerationPrompts] = useState<PromptLibrary | null>(null);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(false);
  const loadedDeckIdRef = useRef<string | null>(null);
  const audioTemplateRef = useRef("");

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
    if (options && mode === "create") {
      const defaults = buildDefaultPrompts(options.defaultGenerationPrompts);
      setFieldSchema(options.defaultFieldSchema);
      setAudioInstructions(options.audioInstructionsTemplate);
      setTargetLanguage(options.targetLanguageOptions[0] ?? "");
      setPrompts(defaults);
      setInitialPrompts(defaults);
      setFullGenerationPrompts({ ...(options.defaultGenerationPrompts ?? {}) });
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
      setInitialPrompts(merged);
    }
  }, [deckData, mode]);

  if (optionsLoading || (mode === "edit" && deckLoading)) {
    return <LoadingScreen label="Loading deck editor" />;
  }

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
      const promptsChanged = initialPrompts ? !promptsEqual(prompts, initialPrompts) : false;
      const generationPromptsPayload = promptsChanged ? mergeGenerationPrompts(fullGenerationPrompts, prompts) : undefined;
      const payload = {
        name,
        targetLanguage,
        fieldSchema,
        audioInstructions,
        audioEnabled,
        generationPrompts: generationPromptsPayload
      };
      if (mode === "create") {
        const response = await apiFetch<{ deck: { id: string } }>("/decks", {
          method: "POST",
          json: payload
        });
        navigate(`/decks/${response.deck.id}`);
      } else if (deckId) {
        await apiFetch(`/decks/${deckId}`, { method: "PUT", json: payload });
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
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <h1 className="text-xl font-semibold text-slate-900">
          {mode === "create" ? "Create deck" : "Edit deck"}
        </h1>
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
        <label className="mt-4 block text-sm text-slate-700 dark:text-slate-300">
          Audio instructions
          <textarea
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
            rows={3}
            value={audioInstructions}
            onChange={(event) => setAudioInstructions(event.target.value)}
          />
        </label>
        <label className="mt-2 flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
          <input type="checkbox" checked={audioEnabled} onChange={(event) => setAudioEnabled(event.target.checked)} />
          Enable audio generation
        </label>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Field schema</h2>
        {options && (
          <FieldSchemaEditor options={options.fieldLibrary} schema={fieldSchema} onChange={setFieldSchema} />
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

      <div className="flex flex-wrap gap-3">
        <button type="submit" className="rounded-full bg-brand px-6 py-3 text-sm font-semibold text-slate-900">
          {mode === "create" ? "Create deck" : "Save changes"}
        </button>
        <button
          type="button"
          className="rounded-full border border-slate-300 px-6 py-3 text-sm dark:border-slate-600 dark:text-slate-200"
          onClick={() => navigate(mode === "create" ? "/decks" : `/decks/${deckId}`)}
        >
          Cancel
        </button>
        {mode === "edit" && deckId && (
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleting}
            className="rounded-full border border-red-400 px-6 py-3 text-sm font-semibold text-red-700 disabled:opacity-60"
          >
            {deleting ? "Deleting…" : "Delete deck"}
          </button>
        )}
      </div>
    </form>
  );
}
