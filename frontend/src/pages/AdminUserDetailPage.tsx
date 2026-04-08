import { FormEvent, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "../lib/api";
import { LoadingScreen } from "../components/LoadingScreen";
import { useSession } from "../lib/session";

interface AdminUser {
  id: string;
  native_language?: string;
  primary_email?: string;
  is_admin: boolean;
  text_model?: string;
  audio_model?: string;
  theme?: string;
  models_locked?: boolean;
}

interface AdminUserDetailResponse {
  user: AdminUser;
  emails: { id: string; email: string; is_primary: boolean }[];
  protectedEmails: string[];
  apiKey: { has_key: boolean; masked?: string };
}

export function AdminUserDetailPage() {
  const { userId } = useParams();
  const session = useSession();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [makePrimary, setMakePrimary] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState("");

  // Settings form state
  const [settingsTextModel, setSettingsTextModel] = useState("");
  const [settingsAudioModel, setSettingsAudioModel] = useState("");
  const [settingsNativeLang, setSettingsNativeLang] = useState("");
  const [settingsTheme, setSettingsTheme] = useState("system");
  const [settingsModelsLocked, setSettingsModelsLocked] = useState(false);
  const [settingsSaved, setSettingsSaved] = useState(false);

  // Model loading/testing state
  const [availableModels, setAvailableModels] = useState<{ textModels: string[]; audioModels: string[] } | null>(null);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [testResult, setTestResult] = useState<{ textModel: { ok: boolean; error?: string | null }; audioModel: { ok: boolean; error?: string | null } } | null>(null);
  const [testing, setTesting] = useState(false);
  const [modelsErr, setModelsErr] = useState("");

  const [actionError, setActionError] = useState("");

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["admin-user", userId],
    queryFn: () => apiFetch<AdminUserDetailResponse>(`/admin/users/${userId}`),
    enabled: session.data?.user.isAdmin && Boolean(userId)
  });

  // Seed settings form from fetched data
  useEffect(() => {
    if (data?.user) {
      setSettingsTextModel(data.user.text_model ?? "");
      setSettingsAudioModel(data.user.audio_model ?? "");
      setSettingsNativeLang(data.user.native_language ?? "");
      setSettingsTheme(data.user.theme ?? "system");
      setSettingsModelsLocked(data.user.models_locked ?? false);
    }
  }, [data?.user]);

  if (!session.data?.user.isAdmin) {
    return <p className="text-sm text-slate-500">Admin access required.</p>;
  }

  if (isLoading) {
    return <LoadingScreen label="Loading user" />;
  }

  if (error) {
    return <p className="text-red-500">Failed to load user: {(error as Error).message}</p>;
  }

  const addEmail = async (event: FormEvent) => {
    event.preventDefault();
    setActionError("");
    try {
      await apiFetch(`/admin/users/${userId}/emails`, {
        method: "POST",
        json: { email, makePrimary }
      });
      setEmail("");
      setMakePrimary(false);
      refetch();
    } catch (err) {
      setActionError((err as Error).message);
    }
  };

  const deleteEmail = async (emailId: string) => {
    setActionError("");
    try {
      await apiFetch(`/admin/users/${userId}/emails/${emailId}`, { method: "DELETE" });
      refetch();
    } catch (err) {
      setActionError((err as Error).message);
    }
  };

  const setPrimaryEmail = async (emailId: string) => {
    setActionError("");
    try {
      await apiFetch(`/admin/users/${userId}/emails/${emailId}/primary`, { method: "POST" });
      refetch();
    } catch (err) {
      setActionError((err as Error).message);
    }
  };

  const renameEmail = async (emailId: string, current: string) => {
    // Use a simple inline form approach instead of window.prompt
    const next = window.prompt("Update email address:", current);
    if (!next || next === current) return;
    setActionError("");
    try {
      await apiFetch(`/admin/users/${userId}/emails/${emailId}`, { method: "PATCH", json: { email: next } });
      refetch();
    } catch (err) {
      setActionError((err as Error).message);
    }
  };

  const toggleAdmin = async (makeAdmin: boolean) => {
    setActionError("");
    try {
      await apiFetch(`/admin/users/${userId}/admin`, { method: "POST", json: { makeAdmin } });
      refetch();
    } catch (err) {
      setActionError((err as Error).message);
    }
  };

  const deleteUser = async () => {
    const confirmed = window.confirm("Delete this user and all their data? This cannot be undone.");
    if (!confirmed) return;
    setActionError("");
    try {
      await apiFetch(`/admin/users/${userId}`, { method: "DELETE" });
      navigate("/admin/users");
    } catch (err) {
      setActionError((err as Error).message);
    }
  };

  const grantApiKey = async (event: FormEvent) => {
    event.preventDefault();
    setActionError("");
    try {
      await apiFetch(`/admin/users/${userId}/api-key`, {
        method: "POST",
        json: { apiKey: apiKeyInput }
      });
      setApiKeyInput("");
      refetch();
    } catch (err) {
      setActionError((err as Error).message);
    }
  };

  const removeApiKey = async () => {
    setActionError("");
    try {
      await apiFetch(`/admin/users/${userId}/api-key`, { method: "DELETE" });
      refetch();
    } catch (err) {
      setActionError((err as Error).message);
    }
  };

  const saveSettings = async () => {
    setActionError("");
    setSettingsSaved(false);
    try {
      await apiFetch(`/admin/users/${userId}/settings`, {
        method: "PUT",
        json: {
          textModel: settingsTextModel.trim() || null,
          audioModel: settingsAudioModel.trim() || null,
          nativeLanguage: settingsNativeLang.trim() || null,
          theme: settingsTheme,
          modelsLocked: settingsModelsLocked,
        }
      });
      refetch();
      setSettingsSaved(true);
      setTimeout(() => setSettingsSaved(false), 3000);
    } catch (err) {
      setActionError((err as Error).message);
    }
  };

  const loadAvailableModels = async () => {
    setModelsLoading(true);
    setModelsErr("");
    try {
      const resp = await apiFetch<{ textModels: string[]; audioModels: string[] }>(`/admin/users/${userId}/models/available`);
      setAvailableModels(resp);
      if (!settingsTextModel && resp.textModels.length) setSettingsTextModel(resp.textModels[0]);
      if (!settingsAudioModel && resp.audioModels.length) setSettingsAudioModel(resp.audioModels[0]);
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
    try {
      const resp = await apiFetch<typeof testResult>(`/admin/users/${userId}/models/test`, {
        method: "POST",
        json: { textModel: settingsTextModel.trim(), audioModel: settingsAudioModel.trim() }
      });
      setTestResult(resp);
    } catch (err) {
      setModelsErr((err as Error).message);
    } finally {
      setTesting(false);
    }
  };

  const handleSettingsTextModelChange = (v: string) => { setSettingsTextModel(v); setTestResult(null); };
  const handleSettingsAudioModelChange = (v: string) => { setSettingsAudioModel(v); setTestResult(null); };

  const protectedEmailSet = new Set((data?.protectedEmails ?? []).map((entry) => entry.toLowerCase()));
  const isProtected = data?.user.primary_email && protectedEmailSet.has(data.user.primary_email.toLowerCase());

  return (
    <div className="space-y-8">
      {actionError && (
        <p className="rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700 dark:bg-red-500/20 dark:text-red-100">
          {actionError}
        </p>
      )}
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">User account</p>
            <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">{data?.user.primary_email ?? "User"}</h1>
            <div className="mt-4 grid gap-4 text-sm sm:grid-cols-2">
              <div className="rounded-2xl border border-slate-100 px-4 py-3 dark:border-slate-800">
                <p className="text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">Native language</p>
                <p className="text-base font-semibold text-slate-900 dark:text-white">{data?.user.native_language ?? "—"}</p>
              </div>
              <div className="rounded-2xl border border-slate-100 px-4 py-3 dark:border-slate-800">
                <p className="text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">Role</p>
                <p className="text-base font-semibold text-slate-900 dark:text-white">
                  {data?.user.is_admin ? "Admin" : "Member"}
                </p>
              </div>
            </div>
            {isProtected && (
              <p className="mt-3 text-xs text-amber-600 dark:text-amber-300">
                Protected system accounts cannot be deleted or demoted.
              </p>
            )}
          </div>
          <div className="flex flex-col gap-3 sm:flex-row lg:flex-col">
            <button
              className="rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-brand hover:text-brand dark:border-slate-600 dark:text-slate-200"
              onClick={() => toggleAdmin(!data?.user.is_admin)}
            >
              {data?.user.is_admin ? "Revoke admin" : "Grant admin"}
            </button>
            {!isProtected && (
              <button
                className="rounded-full border border-red-300 px-4 py-2 text-sm font-semibold text-red-600 hover:bg-red-50 dark:border-red-500/40 dark:text-red-300"
                onClick={deleteUser}
              >
                Delete user
              </button>
            )}
          </div>
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white">OpenAI API key</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">Grant or remove an OpenAI key for this user.</p>
          </div>
          {data?.apiKey?.has_key && (
            <span className="rounded-full border border-emerald-300/60 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 dark:border-emerald-400/40 dark:bg-emerald-400/10 dark:text-emerald-100">
              {data.apiKey.masked ? `On file (${data.apiKey.masked})` : "On file"}
            </span>
          )}
        </div>
        <form className="mt-4 flex flex-col gap-3 sm:flex-row" onSubmit={grantApiKey}>
          <input
            className="flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-white"
            placeholder={data?.apiKey?.has_key ? "Replace key" : "sk-..."}
            value={apiKeyInput}
            onChange={(event) => setApiKeyInput(event.target.value)}
          />
          <button type="submit" className="rounded-full bg-brand px-4 py-2 text-sm font-semibold text-slate-900">
            Grant key
          </button>
          {data?.apiKey?.has_key && (
            <button
              type="button"
              onClick={removeApiKey}
              className="rounded-full border border-red-200 px-4 py-2 text-sm font-semibold text-red-600 dark:border-red-400/40"
            >
              Remove
            </button>
          )}
        </form>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white">User settings</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">Manage this user's models, language, theme, and restrictions.</p>
          </div>
          {!availableModels && (
            <button
              type="button"
              onClick={loadAvailableModels}
              disabled={modelsLoading}
              className="rounded-full border border-slate-300 px-4 py-2 text-sm text-slate-600 disabled:opacity-50 dark:border-slate-600 dark:text-slate-300"
            >
              {modelsLoading ? "Loading..." : "Load models"}
            </button>
          )}
        </div>

        {modelsErr && (
          <p className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-500/20 dark:text-red-100">
            {modelsErr}
          </p>
        )}

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-1.5">
              Text model
            </label>
            <div className="relative">
              {availableModels ? (
                <select
                  className={`w-full rounded-xl border px-3 py-2 text-sm text-slate-900 dark:bg-slate-900 dark:text-white ${
                    testResult
                      ? testResult.textModel.ok
                        ? "border-emerald-400 dark:border-emerald-500"
                        : "border-red-400 dark:border-red-500"
                      : "border-slate-200 dark:border-slate-700"
                  }`}
                  value={settingsTextModel}
                  onChange={(e) => handleSettingsTextModelChange(e.target.value)}
                >
                  {availableModels.textModels.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              ) : (
                <input
                  className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-white"
                  value={settingsTextModel}
                  onChange={(e) => handleSettingsTextModelChange(e.target.value)}
                  placeholder="e.g. gpt-5.4-nano"
                  spellCheck={false}
                  autoCorrect="off"
                  autoCapitalize="off"
                />
              )}
              {testResult && (
                <span className={`absolute right-3 top-1/2 -translate-y-1/2 text-sm font-semibold ${testResult.textModel.ok ? "text-emerald-500" : "text-red-500"}`}>
                  {testResult.textModel.ok ? "\u2713" : "\u2717"}
                </span>
              )}
            </div>
            {testResult?.textModel.error && (
              <p className="mt-1 text-xs text-red-500">{testResult.textModel.error}</p>
            )}
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-1.5">
              Audio model
            </label>
            <div className="relative">
              {availableModels ? (
                <select
                  className={`w-full rounded-xl border px-3 py-2 text-sm text-slate-900 dark:bg-slate-900 dark:text-white ${
                    testResult
                      ? testResult.audioModel.ok
                        ? "border-emerald-400 dark:border-emerald-500"
                        : "border-red-400 dark:border-red-500"
                      : "border-slate-200 dark:border-slate-700"
                  }`}
                  value={settingsAudioModel}
                  onChange={(e) => handleSettingsAudioModelChange(e.target.value)}
                >
                  {availableModels.audioModels.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              ) : (
                <input
                  className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-white"
                  value={settingsAudioModel}
                  onChange={(e) => handleSettingsAudioModelChange(e.target.value)}
                  placeholder="e.g. gpt-4o-mini-tts"
                  spellCheck={false}
                  autoCorrect="off"
                  autoCapitalize="off"
                />
              )}
              {testResult && (
                <span className={`absolute right-3 top-1/2 -translate-y-1/2 text-sm font-semibold ${testResult.audioModel.ok ? "text-emerald-500" : "text-red-500"}`}>
                  {testResult.audioModel.ok ? "\u2713" : "\u2717"}
                </span>
              )}
            </div>
            {testResult?.audioModel.error && (
              <p className="mt-1 text-xs text-red-500">{testResult.audioModel.error}</p>
            )}
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-1.5">
              Native language
            </label>
            <input
              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-white"
              value={settingsNativeLang}
              onChange={(e) => setSettingsNativeLang(e.target.value)}
              placeholder="e.g. English"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-1.5">
              Theme
            </label>
            <select
              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-white"
              value={settingsTheme}
              onChange={(e) => setSettingsTheme(e.target.value)}
            >
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </div>
        </div>

        <div className="mt-4">
          <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-slate-300 text-brand focus:ring-brand"
              checked={settingsModelsLocked}
              onChange={(e) => setSettingsModelsLocked(e.target.checked)}
            />
            Lock model settings
          </label>
          <p className="mt-1 ml-6 text-xs text-slate-500 dark:text-slate-400">
            When enabled, this user cannot change their own model preferences.
          </p>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={testModels}
            disabled={testing || !settingsTextModel.trim() || !settingsAudioModel.trim()}
            className="rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-50 dark:border-slate-600 dark:text-slate-200"
          >
            {testing ? "Testing..." : "Test models"}
          </button>
          <button
            type="button"
            onClick={saveSettings}
            className="rounded-full bg-brand px-4 py-2 text-sm font-semibold text-slate-900"
          >
            Save settings
          </button>
          {settingsSaved && (
            <span className="text-sm text-emerald-600 dark:text-emerald-400">Saved.</span>
          )}
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Email addresses</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">Primary email is used for login, others for alerts.</p>
          </div>
        </div>
        <div className="mt-4 space-y-3">
          {data?.emails.map((item) => {
            const locked = protectedEmailSet.has(item.email.toLowerCase());
            return (
              <div
                key={item.id}
                className="flex flex-col gap-3 rounded-2xl border border-slate-100 p-4 text-sm dark:border-slate-800 dark:bg-slate-900/60 md:flex-row md:items-center md:justify-between"
              >
                <div>
                  <p className="font-medium text-slate-900 dark:text-white">{item.email}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                    {item.is_primary && (
                      <span className="rounded-full border border-emerald-400/70 px-2 py-0.5 text-emerald-700 dark:border-emerald-500/40 dark:text-emerald-200">
                        Primary
                      </span>
                    )}
                    {locked && (
                      <span className="rounded-full border border-amber-400/70 px-2 py-0.5 text-amber-700 dark:border-amber-500/40 dark:text-amber-200">
                        Protected
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 text-xs font-semibold text-slate-600 dark:text-slate-200">
                  <button type="button" className="text-brand" onClick={() => renameEmail(item.id, item.email)}>
                    Rename
                  </button>
                  {!item.is_primary && (
                    <button type="button" className="text-brand" onClick={() => setPrimaryEmail(item.id)}>
                      Make primary
                    </button>
                  )}
                  {!item.is_primary && !locked && (
                    <button type="button" className="text-red-500" onClick={() => deleteEmail(item.id)}>
                      Delete
                    </button>
                  )}
                </div>
              </div>
            );
          })}
          {!data?.emails?.length && (
            <div className="rounded-2xl border border-dashed border-slate-200 p-6 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
              No email addresses.
            </div>
          )}
        </div>
        <form className="mt-6 grid gap-3 md:grid-cols-[2fr_auto_auto]" onSubmit={addEmail}>
          <input
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-white"
            placeholder="new@example.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-slate-300 text-brand focus:ring-brand"
              checked={makePrimary}
              onChange={(event) => setMakePrimary(event.target.checked)}
            />
            Make primary
          </label>
          <button type="submit" className="rounded-full bg-brand px-4 py-2 text-sm font-semibold text-slate-900">
            Add email
          </button>
        </form>
      </section>
    </div>
  );
}
