import { FormEvent, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "../lib/api";
import { LoadingScreen } from "../components/LoadingScreen";
import { getCloudflareLogoutUrl } from "../lib/logout";
import { ThemeToggle } from "../components/ThemeToggle";

interface ProfileResponse {
  user: {
    id: string;
    nativeLanguage?: string;
    primaryEmail?: string;
    isAdmin: boolean;
    textModel?: string;
    audioModel?: string;
    modelsLocked?: boolean;
  };
  emails: { id: string; email: string; is_primary: boolean }[];
  apiKey: { has_key: boolean; masked?: string };
  nativeLanguageOptions: string[];
}

interface AvailableModelsResponse {
  textModels: string[];
  audioModels: string[];
  defaultTextModel: string;
  defaultAudioModel: string;
}

interface ModelTestResult {
  ok: boolean;
  error?: string | null;
}
interface ModelTestResponse {
  textModel: ModelTestResult;
  audioModel: ModelTestResult;
}

export function ProfilePage() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["profile"],
    queryFn: () => apiFetch<ProfileResponse>("/profile")
  });
  const [apiKey, setApiKey] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [message, setMessage] = useState("");
  const [errMsg, setErrMsg] = useState("");

  // Model prefs state
  const [textModel, setTextModel] = useState("");
  const [audioModel, setAudioModel] = useState("");
  const [availableModels, setAvailableModels] = useState<AvailableModelsResponse | null>(null);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [testResult, setTestResult] = useState<ModelTestResponse | null>(null);
  const [testing, setTesting] = useState(false);
  const [modelsSaved, setModelsSaved] = useState(false);
  const [modelsErr, setModelsErr] = useState("");

  // Seed model inputs from profile
  useEffect(() => {
    if (data?.user) {
      setTextModel(data.user.textModel ?? "gpt-5.4-nano");
      setAudioModel(data.user.audioModel ?? "gpt-4o-mini-tts");
    }
  }, [data?.user]);

  if (isLoading) return <LoadingScreen label="Loading profile" />;
  if (error) return <p className="text-red-500">Failed to load profile: {(error as Error).message}</p>;

  const emails = data?.emails ?? [];
  const user = data?.user;
  const nativeLanguage = user?.nativeLanguage || "Not set";
  const primaryEmail = emails.find((e) => e.is_primary)?.email || user?.primaryEmail || "—";
  const hasApiKey = Boolean(data?.apiKey?.has_key);
  const modelsLocked = Boolean(user?.modelsLocked);
  const logoutHref = getCloudflareLogoutUrl();

  const handleApiKey = async (event: FormEvent) => {
    event.preventDefault();
    setErrMsg("");
    try {
      await apiFetch("/profile/api-key", { method: "POST", json: { apiKey } });
      setApiKey("");
      refetch();
      setMessage("API key saved.");
    } catch (err) {
      setErrMsg((err as Error).message);
    }
  };

  const removeApiKey = async () => {
    setErrMsg("");
    try {
      await apiFetch("/profile/api-key", { method: "DELETE" });
      refetch();
      setMessage("API key removed.");
    } catch (err) {
      setErrMsg((err as Error).message);
    }
  };

  const addEmail = async (event: FormEvent) => {
    event.preventDefault();
    setErrMsg("");
    try {
      await apiFetch("/profile/emails", { method: "POST", json: { email: newEmail, makePrimary: false } });
      setNewEmail("");
      refetch();
      setMessage("Email added.");
    } catch (err) {
      setErrMsg((err as Error).message);
    }
  };

  const deleteEmail = async (id: string) => {
    setErrMsg("");
    try {
      await apiFetch(`/profile/emails/${id}`, { method: "DELETE" });
      refetch();
    } catch (err) {
      setErrMsg((err as Error).message);
    }
  };

  const setPrimaryEmail = async (id: string) => {
    setErrMsg("");
    try {
      await apiFetch(`/profile/emails/${id}/primary`, { method: "POST" });
      refetch();
    } catch (err) {
      setErrMsg((err as Error).message);
    }
  };

  const deleteAccount = async () => {
    const confirmed = window.confirm("Delete your profile and all decks?");
    if (!confirmed) return;
    const response = await apiFetch<{ logoutUrl?: string }>("/profile", { method: "DELETE" });
    window.location.href = response.logoutUrl ?? getCloudflareLogoutUrl();
  };

  const loadAvailableModels = async () => {
    setModelsLoading(true);
    setModelsErr("");
    try {
      const resp = await apiFetch<AvailableModelsResponse>("/profile/models/available");
      setAvailableModels(resp);
      // Seed inputs if user hasn't set a preference yet
      if (!textModel && resp.defaultTextModel) setTextModel(resp.defaultTextModel);
      if (!audioModel && resp.defaultAudioModel) setAudioModel(resp.defaultAudioModel);
    } catch (err) {
      setModelsErr((err as Error).message);
    } finally {
      setModelsLoading(false);
    }
  };

  const testModels = async () => {
    setTesting(true);
    setModelsErr("");
    setTestResult(null);
    setModelsSaved(false);
    try {
      const resp = await apiFetch<ModelTestResponse>("/profile/models/test", {
        method: "POST",
        json: { textModel: textModel.trim(), audioModel: audioModel.trim() },
      });
      setTestResult(resp);
    } catch (err) {
      setModelsErr((err as Error).message);
    } finally {
      setTesting(false);
    }
  };

  const saveModelPrefs = async () => {
    setModelsErr("");
    setModelsSaved(false);
    try {
      await apiFetch("/profile/models", {
        method: "PUT",
        json: { textModel: textModel.trim() || null, audioModel: audioModel.trim() || null },
      });
      refetch();
      setModelsSaved(true);
      setTimeout(() => setModelsSaved(false), 3000);
    } catch (err) {
      setModelsErr((err as Error).message);
    }
  };

  // Reset test result whenever the user changes a model name
  const handleTextModelChange = (v: string) => { setTextModel(v); setTestResult(null); setModelsSaved(false); };
  const handleAudioModelChange = (v: string) => { setAudioModel(v); setTestResult(null); setModelsSaved(false); };



  return (
    <div className="mx-auto max-w-4xl space-y-5">
      {message && (
        <p className="rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:bg-emerald-400/20 dark:text-emerald-100">
          {message}
        </p>
      )}
      {errMsg && (
        <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-500/20 dark:text-red-100">
          {errMsg}
        </p>
      )}

      {/* Profile summary */}
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-slate-900 dark:text-white">Profile</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">{primaryEmail}</p>
          </div>
          <a
            className="rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 dark:border-slate-600 dark:text-slate-200"
            href={logoutHref}
          >
            Log out
          </a>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 text-sm">
          <div className="rounded-2xl border border-slate-100 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-900/60">
            <p className="text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">Language</p>
            <p className="mt-1 font-semibold text-slate-900 dark:text-white">{nativeLanguage}</p>
          </div>
          <div className="rounded-2xl border border-slate-100 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-900/60">
            <p className="text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">API key</p>
            <p className="mt-1 font-semibold text-slate-900 dark:text-white">
              {hasApiKey ? data?.apiKey?.masked ?? "On file" : "Not set"}
            </p>
          </div>
          <div className="col-span-2 sm:col-span-1 rounded-2xl border border-slate-100 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-900/60">
            <p className="text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">Text model</p>
            <p className="mt-1 font-semibold text-slate-900 dark:text-white truncate">{user?.textModel || "gpt-5.4-nano"}</p>
          </div>
        </div>
      </section>

      {/* OpenAI API key */}
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-base font-semibold text-slate-900 dark:text-white">OpenAI API key</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">Your own key for billing control.</p>
          </div>
          {hasApiKey && (
            <span className="rounded-full border border-emerald-300/60 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 dark:border-emerald-400/40 dark:bg-emerald-400/10 dark:text-emerald-100">
              On file
            </span>
          )}
        </div>
        <form className="mt-4 flex flex-col gap-3 sm:flex-row" onSubmit={handleApiKey}>
          <input
            className="flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm dark:border-slate-700 dark:bg-slate-900"
            placeholder={hasApiKey ? "Replace key" : "sk-..."}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
          <button type="submit" className="rounded-full bg-brand px-5 py-2.5 text-sm font-semibold text-slate-900 min-h-[44px]">
            Save key
          </button>
          {hasApiKey && (
            <button
              type="button"
              onClick={removeApiKey}
              className="rounded-full border border-red-200 px-5 py-2.5 text-sm font-semibold text-red-600 min-h-[44px] dark:border-red-400/40"
            >
              Remove
            </button>
          )}
        </form>
      </section>

      {/* Theme */}
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-slate-900 dark:text-white">Appearance</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Stored to your account — applies on any device you log in from.
            </p>
          </div>
          <ThemeToggle />
        </div>
      </section>

      {/* Model selection */}
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-base font-semibold text-slate-900 dark:text-white">AI Models</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {modelsLocked
                ? "Your model settings are managed by an administrator."
                : "Choose models for text and audio generation. Test before saving."}
            </p>
          </div>
          {!modelsLocked && !availableModels && (
            <button
              type="button"
              onClick={loadAvailableModels}
              disabled={modelsLoading}
              className="rounded-full border border-slate-300 px-4 py-2 text-sm text-slate-600 disabled:opacity-50 dark:border-slate-600 dark:text-slate-300 min-h-[44px]"
            >
              {modelsLoading ? "Loading…" : "Load models"}
            </button>
          )}
        </div>

        {modelsErr && (
          <p className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-500/20 dark:text-red-100">
            {modelsErr}
          </p>
        )}

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          {/* Text model */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-1.5">
              Text model
            </label>
            <div className="relative">
              {availableModels && !modelsLocked ? (
                <select
                  className={`w-full rounded-xl border px-3 py-2.5 text-sm dark:bg-slate-900 dark:text-white ${
                    testResult
                      ? testResult.textModel.ok
                        ? "border-emerald-400 dark:border-emerald-500"
                        : "border-red-400 dark:border-red-500"
                      : "border-slate-200 dark:border-slate-700"
                  }`}
                  value={textModel}
                  onChange={(e) => handleTextModelChange(e.target.value)}
                >
                  {availableModels.textModels.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              ) : (
                <input
                  className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-white disabled:opacity-60 disabled:cursor-not-allowed"
                  value={textModel}
                  onChange={(e) => handleTextModelChange(e.target.value)}
                  placeholder="e.g. gpt-5.4-nano"
                  spellCheck={false}
                  autoCorrect="off"
                  autoCapitalize="off"
                  disabled={modelsLocked}
                />
              )}
              {testResult && (
                <span className={`absolute right-3 top-1/2 -translate-y-1/2 text-sm font-semibold ${testResult.textModel.ok ? "text-emerald-500" : "text-red-500"}`}>
                  {testResult.textModel.ok ? "✓" : "✗"}
                </span>
              )}
            </div>
            {testResult?.textModel.error && (
              <p className="mt-1 text-xs text-red-500">{testResult.textModel.error}</p>
            )}
          </div>

          {/* Audio model */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-1.5">
              Audio model
            </label>
            <div className="relative">
              {availableModels && !modelsLocked ? (
                <select
                  className={`w-full rounded-xl border px-3 py-2.5 text-sm dark:bg-slate-900 dark:text-white ${
                    testResult
                      ? testResult.audioModel.ok
                        ? "border-emerald-400 dark:border-emerald-500"
                        : "border-red-400 dark:border-red-500"
                      : "border-slate-200 dark:border-slate-700"
                  }`}
                  value={audioModel}
                  onChange={(e) => handleAudioModelChange(e.target.value)}
                >
                  {availableModels.audioModels.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              ) : (
                <input
                  className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-white disabled:opacity-60 disabled:cursor-not-allowed"
                  value={audioModel}
                  onChange={(e) => handleAudioModelChange(e.target.value)}
                  placeholder="e.g. gpt-4o-mini-tts"
                  spellCheck={false}
                  autoCorrect="off"
                  autoCapitalize="off"
                  disabled={modelsLocked}
                />
              )}
              {testResult && (
                <span className={`absolute right-3 top-1/2 -translate-y-1/2 text-sm font-semibold ${testResult.audioModel.ok ? "text-emerald-500" : "text-red-500"}`}>
                  {testResult.audioModel.ok ? "✓" : "✗"}
                </span>
              )}
            </div>
            {testResult?.audioModel.error && (
              <p className="mt-1 text-xs text-red-500">{testResult.audioModel.error}</p>
            )}
          </div>
        </div>

        {!modelsLocked && (
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={testModels}
              disabled={testing || !textModel.trim() || !audioModel.trim()}
              className="rounded-full border border-slate-300 px-5 py-2.5 text-sm font-semibold text-slate-700 disabled:opacity-50 dark:border-slate-600 dark:text-slate-200 min-h-[44px]"
            >
              {testing ? "Testing…" : "Test"}
            </button>
            <button
              type="button"
              onClick={saveModelPrefs}
              disabled={!textModel.trim() || !audioModel.trim()}
              className="rounded-full bg-brand px-5 py-2.5 text-sm font-semibold text-slate-900 disabled:opacity-40 min-h-[44px]"
            >
              Save
            </button>
            {modelsSaved && (
              <span className="text-sm text-emerald-600 dark:text-emerald-400">Saved.</span>
            )}
          </div>
        )}
      </section>

      {/* Emails */}
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <h2 className="text-base font-semibold text-slate-900 dark:text-white">Email addresses</h2>
        <ul className="mt-3 divide-y divide-slate-100 text-sm dark:divide-slate-800">
          {emails.map((email) => (
            <li key={email.id} className="flex items-center justify-between py-3 gap-2">
              <div>
                <p className="font-medium text-slate-900 dark:text-white">{email.email}</p>
                {email.is_primary && <span className="text-xs text-slate-400 dark:text-slate-500">Primary</span>}
              </div>
              <div className="flex gap-3 text-xs shrink-0">
                {!email.is_primary && (
                  <button className="text-brand" onClick={() => setPrimaryEmail(email.id)}>Make primary</button>
                )}
                {!email.is_primary && (
                  <button className="text-red-500" onClick={() => deleteEmail(email.id)}>Remove</button>
                )}
              </div>
            </li>
          ))}
        </ul>
        <form className="mt-4 flex flex-col gap-3 sm:flex-row" onSubmit={addEmail}>
          <input
            className="flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm dark:border-slate-700 dark:bg-slate-900"
            placeholder="new@example.com"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
          />
          <button type="submit" className="rounded-full bg-brand px-5 py-2.5 text-sm font-semibold text-slate-900 min-h-[44px]">
            Add email
          </button>
        </form>
      </section>

      {/* Danger zone */}
      <section className="rounded-3xl border border-red-200 bg-red-50 p-5 shadow-sm dark:border-red-400/50 dark:bg-red-500/10">
        <h2 className="text-base font-semibold text-red-900 dark:text-red-200">Danger zone</h2>
        <p className="mt-1 text-sm text-red-800 dark:text-red-300">Permanently delete your account and all decks.</p>
        <button
          type="button"
          onClick={deleteAccount}
          className="mt-4 rounded-full border border-red-400 px-5 py-2.5 text-sm font-semibold text-red-700 min-h-[44px] dark:border-red-300 dark:text-red-100"
        >
          Delete account
        </button>
      </section>
    </div>
  );
}
