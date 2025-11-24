import { FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { apiFetch } from "../lib/api";
import { LoadingScreen } from "../components/LoadingScreen";
import { useSession } from "../lib/session";

interface AdminUsersResponse {
  users: { id: string; primary_email: string; native_language?: string; is_admin: boolean }[];
  protectedEmails: string[];
}

type GenerationKey = "translation" | "reverse_translation" | "dictionary" | "sentence";

interface PromptFace {
  front: string;
  back: string;
}

interface GenerationPrompt {
  system: string;
  user: string;
}

interface AudioPromptConfig {
  instructions: string;
  enabled: boolean;
}

interface PromptTemplates {
  forward: PromptFace;
  backward: PromptFace;
  generation: Record<GenerationKey, GenerationPrompt>;
  audio: AudioPromptConfig;
}

type PromptTemplatesInput = Partial<{
  forward: Partial<PromptFace>;
  backward: Partial<PromptFace>;
  generation: Partial<Record<GenerationKey, Partial<GenerationPrompt>>>;
  audio: Partial<AudioPromptConfig>;
}>;

interface PromptTemplatesResponse {
  promptTemplates: PromptTemplatesInput;
}

const GENERATION_SECTIONS: { key: GenerationKey; label: string; helper: string }[] = [
  { key: "translation", label: "Foreign → Native", helper: "Fills the learner's native phrase field." },
  { key: "reverse_translation", label: "Native → Foreign", helper: "Used when generating backward cards." },
  { key: "dictionary", label: "Dictionary entry", helper: "Populates the notes / grammar field." },
  { key: "sentence", label: "Example sentence", helper: "Creates a short usage sentence." }
];

function normalizePromptTemplates(raw?: PromptTemplatesInput | PromptTemplates | null): PromptTemplates {
  const ensureFace = (face?: Partial<PromptFace>): PromptFace => ({
    front: face?.front ?? "",
    back: face?.back ?? ""
  });

  const ensureGeneration = (key: GenerationKey): GenerationPrompt => {
    const generation = raw?.generation ?? {};
    const value = generation[key];
    return {
      system: value?.system ?? "",
      user: value?.user ?? ""
    };
  };

  return {
    forward: ensureFace(raw?.forward as PromptFace | undefined),
    backward: ensureFace(raw?.backward as PromptFace | undefined),
    generation: {
      translation: ensureGeneration("translation"),
      reverse_translation: ensureGeneration("reverse_translation"),
      dictionary: ensureGeneration("dictionary"),
      sentence: ensureGeneration("sentence")
    },
    audio: {
      instructions: raw?.audio?.instructions ?? "",
      enabled: raw?.audio?.enabled ?? true
    }
  };
}

export function AdminUsersPage() {
  const session = useSession();
  const queryClient = useQueryClient();
  const [promptDraft, setPromptDraft] = useState<PromptTemplates | null>(null);

  const {
    data,
    isLoading,
    error
  } = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => apiFetch<AdminUsersResponse>("/admin/users"),
    enabled: session.data?.user.isAdmin
  });

  const promptQuery = useQuery({
    queryKey: ["admin-default-prompts"],
    queryFn: () => apiFetch<PromptTemplatesResponse>("/admin/default-prompts"),
    enabled: session.data?.user.isAdmin
  });

  useEffect(() => {
    if (promptQuery.data?.promptTemplates) {
      setPromptDraft(normalizePromptTemplates(promptQuery.data.promptTemplates));
    }
  }, [promptQuery.data]);

  const savePrompts = useMutation({
    mutationFn: (payload: PromptTemplates) =>
      apiFetch<PromptTemplatesResponse>("/admin/default-prompts", {
        method: "PUT",
        json: { promptTemplates: payload }
      }),
    onSuccess: (response) => {
      const normalized = normalizePromptTemplates(response.promptTemplates);
      setPromptDraft(normalized);
      queryClient.setQueryData(["admin-default-prompts"], response);
    }
  });

  const protectedEmails = useMemo(() => {
    return new Set((data?.protectedEmails ?? []).map((entry) => entry.toLowerCase()));
  }, [data?.protectedEmails]);

  const totalUsers = data?.users?.length ?? 0;
  const adminCount = data?.users?.filter((user) => user.is_admin).length ?? 0;
  const promptError = promptQuery.error as Error | null;

  if (!session.data?.user.isAdmin) {
    return <p className="text-sm text-slate-500">Admin access required.</p>;
  }

  if (isLoading) {
    return <LoadingScreen label="Loading users" />;
  }

  if (error) {
    return <p className="text-red-500">Failed to load users: {(error as Error).message}</p>;
  }

  const updateCardTemplate = (direction: "forward" | "backward", face: "front" | "back", value: string) => {
    setPromptDraft((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        [direction]: {
          ...prev[direction],
          [face]: value
        }
      };
    });
  };

  const updateGenerationPrompt = (key: GenerationKey, field: "system" | "user", value: string) => {
    setPromptDraft((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        generation: {
          ...prev.generation,
          [key]: {
            ...prev.generation[key],
            [field]: value
          }
        }
      };
    });
  };

  const handleAudioInstructions = (value: string) => {
    setPromptDraft((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        audio: {
          ...prev.audio,
          instructions: value
        }
      };
    });
  };

  const toggleAudioEnabled = (value: boolean) => {
    setPromptDraft((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        audio: {
          ...prev.audio,
          enabled: value
        }
      };
    });
  };

  const handlePromptSave = (event: FormEvent) => {
    event.preventDefault();
    if (!promptDraft || savePrompts.isPending) return;
    savePrompts.mutate(promptDraft);
  };

  return (
    <div className="space-y-8">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Admin · Control center</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Manage users, protective flags, and the default prompts applied to new decks.
            </p>
          </div>
          <Link
            to="/decks/new"
            className="inline-flex items-center justify-center rounded-full bg-brand px-4 py-2 text-sm font-semibold text-slate-900"
          >
            Create deck
          </Link>
        </div>
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <div className="rounded-2xl border border-slate-100 px-4 py-3 dark:border-slate-800">
            <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Total users</p>
            <p className="text-3xl font-semibold text-slate-900 dark:text-white">{totalUsers}</p>
          </div>
          <div className="rounded-2xl border border-slate-100 px-4 py-3 dark:border-slate-800">
            <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Admins</p>
            <p className="text-3xl font-semibold text-slate-900 dark:text-white">{adminCount}</p>
          </div>
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Accounts</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">Track every profile plus its admin status.</p>
          </div>
        </div>
        <div className="mt-4 overflow-x-auto rounded-2xl border border-slate-100 dark:border-slate-800">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500 dark:bg-slate-900/40 dark:text-slate-300">
              <tr>
                <th className="px-4 py-3 font-medium">User</th>
                <th className="px-4 py-3 font-medium">Native language</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {data?.users?.map((user) => {
                const isProtected = protectedEmails.has((user.primary_email ?? "").toLowerCase());
                return (
                  <tr key={user.id}>
                    <td className="px-4 py-4">
                      <div className="font-medium text-slate-900 dark:text-white">{user.primary_email ?? "—"}</div>
                      <p className="text-xs text-slate-500 dark:text-slate-400">{isProtected ? "Protected admin" : "Standard user"}</p>
                    </td>
                    <td className="px-4 py-4 text-slate-600 dark:text-slate-300">{user.native_language ?? "—"}</td>
                    <td className="px-4 py-4">
                      <span
                        className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${
                          user.is_admin
                            ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-100"
                            : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200"
                        }`}
                      >
                        {user.is_admin ? "Admin" : "Member"}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-right">
                      <Link
                        to={`/admin/users/${user.id}`}
                        className="rounded-full border border-slate-300 px-3 py-1 text-xs font-medium text-slate-600 hover:border-brand hover:text-brand dark:border-slate-600 dark:text-slate-200"
                      >
                        Manage
                      </Link>
                    </td>
                  </tr>
                );
              })}
              {!data?.users?.length && (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-sm text-slate-500 dark:text-slate-400">
                    No users found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Default prompts</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              These templates seed every new deck. Update them to steer card layouts, generation, and audio tone.
            </p>
          </div>
          {savePrompts.isSuccess && (
            <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">Defaults updated.</span>
          )}
        </div>
        {promptError && (
          <p className="mt-4 text-sm text-red-500">Failed to load default prompts: {promptError.message}</p>
        )}
        <form className="mt-6 space-y-6" onSubmit={handlePromptSave}>
          <div className="grid gap-4 md:grid-cols-2">
            {(["forward", "backward"] as const).map((direction) => (
              <div key={direction} className="rounded-2xl border border-slate-100 p-4 dark:border-slate-800 dark:bg-slate-900/50">
                <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-300">
                  {direction === "forward" ? "Forward card" : "Backward card"}
                </h3>
                <label className="mt-3 block text-xs font-medium uppercase text-slate-400 dark:text-slate-500">
                  Front template
                </label>
                <textarea
                  className="mt-1 h-28 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-white"
                  value={promptDraft?.[direction]?.front ?? ""}
                  disabled={!promptDraft || savePrompts.isPending || promptQuery.isLoading}
                  onChange={(event) => updateCardTemplate(direction, "front", event.target.value)}
                />
                <label className="mt-3 block text-xs font-medium uppercase text-slate-400 dark:text-slate-500">
                  Back template
                </label>
                <textarea
                  className="mt-1 h-28 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-white"
                  value={promptDraft?.[direction]?.back ?? ""}
                  disabled={!promptDraft || savePrompts.isPending || promptQuery.isLoading}
                  onChange={(event) => updateCardTemplate(direction, "back", event.target.value)}
                />
                <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                  Use variables like <code className="rounded bg-slate-100 px-1 text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-200">&#123;&#123;foreign_phrase&#125;&#125;</code>.{" "}
                  <Link to="/help" className="font-semibold text-brand">
                    View the full variable list
                  </Link>
                  .
                </p>
              </div>
            ))}
          </div>

          <div className="space-y-4 rounded-2xl border border-slate-100 p-4 dark:border-slate-800 dark:bg-slate-900/50">
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-300">Generation prompts</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">Fine tune the system + user instructions we send to the LLM.</p>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              {GENERATION_SECTIONS.map((section) => (
                <div key={section.key} className="rounded-xl border border-slate-100 p-3 dark:border-slate-800">
                  <p className="text-sm font-semibold text-slate-800 dark:text-white">{section.label}</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">{section.helper}</p>
                  <label className="mt-3 block text-xs font-medium uppercase text-slate-400 dark:text-slate-500">System</label>
                  <textarea
                    className="mt-1 h-20 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-white"
                    value={promptDraft?.generation?.[section.key]?.system ?? ""}
                    disabled={!promptDraft || savePrompts.isPending || promptQuery.isLoading}
                    onChange={(event) => updateGenerationPrompt(section.key, "system", event.target.value)}
                  />
                  <label className="mt-3 block text-xs font-medium uppercase text-slate-400 dark:text-slate-500">User</label>
                  <textarea
                    className="mt-1 h-24 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-white"
                    value={promptDraft?.generation?.[section.key]?.user ?? ""}
                    disabled={!promptDraft || savePrompts.isPending || promptQuery.isLoading}
                    onChange={(event) => updateGenerationPrompt(section.key, "user", event.target.value)}
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-100 p-4 dark:border-slate-800 dark:bg-slate-900/50">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-300">Audio defaults</h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">Voice instructions and whether TTS is on by default.</p>
              </div>
              <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-200">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-slate-300 text-brand focus:ring-brand"
                  checked={promptDraft?.audio?.enabled ?? true}
                  disabled={!promptDraft || savePrompts.isPending || promptQuery.isLoading}
                  onChange={(event) => toggleAudioEnabled(event.target.checked)}
                />
                Audio enabled
              </label>
            </div>
            <textarea
              className="mt-3 h-28 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-white"
              value={promptDraft?.audio?.instructions ?? ""}
              disabled={!promptDraft || savePrompts.isPending || promptQuery.isLoading}
              onChange={(event) => handleAudioInstructions(event.target.value)}
            />
            <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">Supports the &#123;target_language&#125; placeholder.</p>
          </div>

          <div className="flex flex-col gap-3 border-t border-dashed border-slate-200 pt-4 dark:border-slate-800 sm:flex-row sm:items-center sm:justify-between">
            {savePrompts.error && (
              <p className="text-sm text-red-500">Failed to save prompts: {(savePrompts.error as Error).message}</p>
            )}
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
              {promptQuery.isLoading && (
                <span className="text-xs text-slate-500 dark:text-slate-400">Loading current defaults…</span>
              )}
              <button
                type="submit"
                className="rounded-full bg-brand px-4 py-2 text-sm font-semibold text-slate-900 disabled:opacity-60"
                disabled={!promptDraft || savePrompts.isPending}
              >
                {savePrompts.isPending ? "Saving…" : "Save default prompts"}
              </button>
            </div>
          </div>
        </form>
      </section>
    </div>
  );
}
