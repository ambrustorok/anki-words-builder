import { FormEvent, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "../lib/api";
import { LoadingScreen } from "../components/LoadingScreen";
import { getCloudflareLogoutUrl } from "../lib/logout";

interface ProfileResponse {
  user: {
    id: string;
    nativeLanguage?: string;
    primaryEmail?: string;
    isAdmin: boolean;
  };
  emails: { id: string; email: string; is_primary: boolean }[];
  apiKey: { has_key: boolean; masked?: string };
  nativeLanguageOptions: string[];
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

  if (isLoading) {
    return <LoadingScreen label="Loading profile" />;
  }
  if (error) {
    return <p className="text-red-500">Failed to load profile: {(error as Error).message}</p>;
  }
  const emails = data?.emails ?? [];
  const user = data?.user;
  const nativeLanguage = user?.nativeLanguage || "Not set";
  const primaryEmail = emails.find((email) => email.is_primary)?.email || user?.primaryEmail || "—";
  const hasApiKey = Boolean(data?.apiKey?.has_key);
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
    await apiFetch("/profile/api-key", { method: "DELETE" });
    refetch();
    setMessage("API key removed.");
  };

  const addEmail = async (event: FormEvent) => {
    event.preventDefault();
    setErrMsg("");
    try {
      await apiFetch("/profile/emails", {
        method: "POST",
        json: { email: newEmail, makePrimary: false }
      });
      setNewEmail("");
      refetch();
      setMessage("Email added. You can set it as primary below.");
    } catch (err) {
      setErrMsg((err as Error).message);
    }
  };

  const deleteEmail = async (id: string) => {
    await apiFetch(`/profile/emails/${id}`, { method: "DELETE" });
    refetch();
  };

  const setPrimaryEmail = async (id: string) => {
    await apiFetch(`/profile/emails/${id}/primary`, { method: "POST" });
    refetch();
  };

  const deleteAccount = async () => {
    const confirmed = window.confirm("Delete your profile and all decks?");
    if (!confirmed) return;
    const response = await apiFetch<{ logoutUrl?: string }>("/profile", { method: "DELETE" });
    window.location.href = response.logoutUrl ?? getCloudflareLogoutUrl();
  };

  return (
    <div className="space-y-6">
      {message && <p className="rounded-lg bg-emerald-50 px-4 py-2 text-sm text-emerald-700 dark:bg-emerald-400/20 dark:text-emerald-100">{message}</p>}
      {errMsg && <p className="rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700 dark:bg-red-500/20 dark:text-red-100">{errMsg}</p>}

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-slate-900 dark:text-white">Profile</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">Review your account details and API access.</p>
          </div>
          <a
            className="rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-400 dark:border-slate-600 dark:text-slate-200"
            href={logoutHref}
          >
            Log out
          </a>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-900/60">
            <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Native language</p>
            <p className="mt-1 text-base font-semibold text-slate-900 dark:text-white">{nativeLanguage}</p>
            <p className="text-xs text-slate-500 dark:text-slate-400">Set during onboarding</p>
          </div>
          <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-900/60">
            <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Primary email</p>
            <p className="mt-1 text-base font-semibold text-slate-900 dark:text-white">{primaryEmail}</p>
            <p className="text-xs text-slate-500 dark:text-slate-400">Used for notifications</p>
          </div>
          <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-900/60">
            <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">API key</p>
            <p className="mt-1 text-base font-semibold text-slate-900 dark:text-white">
              {hasApiKey ? `On file (${data?.apiKey?.masked ?? "••••"})` : "Using server default"}
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400">{hasApiKey ? "Custom key stored securely" : "Add your own to control usage"}</p>
          </div>
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">OpenAI API key</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">Provide your own key to control billing and rate limits.</p>
          </div>
          {hasApiKey && (
            <span className="inline-flex items-center rounded-full border border-emerald-300/60 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 dark:border-emerald-400/40 dark:bg-emerald-400/10 dark:text-emerald-100">
              Key on file
            </span>
          )}
        </div>
        <form className="mt-4 flex flex-col gap-3 md:flex-row" onSubmit={handleApiKey}>
          <input
            className="flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
            placeholder={hasApiKey ? "Update key" : "sk-..."}
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
          />
          <button type="submit" className="rounded-full bg-brand px-4 py-2 text-sm font-semibold text-slate-900">
            Save key
          </button>
          {hasApiKey && (
            <button
              type="button"
              onClick={removeApiKey}
              className="rounded-full border border-red-200 px-4 py-2 text-sm font-semibold text-red-600 dark:border-red-400/40"
            >
              Delete key
            </button>
          )}
        </form>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Emails</h2>
        <ul className="mt-4 divide-y divide-slate-100 text-sm dark:divide-slate-800">
          {emails.map((email) => (
            <li key={email.id} className="flex items-center justify-between py-3">
              <div>
                <p className="font-medium text-slate-900 dark:text-white">{email.email}</p>
                {email.is_primary && <span className="text-xs text-slate-500 dark:text-slate-400">Primary</span>}
              </div>
              <div className="flex gap-2 text-xs">
                {!email.is_primary && (
                  <button className="text-brand" onClick={() => setPrimaryEmail(email.id)}>
                    Make primary
                  </button>
                )}
                {!email.is_primary && (
                  <button className="text-red-500" onClick={() => deleteEmail(email.id)}>
                    Delete
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
        <form className="mt-4 flex flex-col gap-3 md:flex-row" onSubmit={addEmail}>
          <input
            className="flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
            placeholder="new@example.com"
            value={newEmail}
            onChange={(event) => setNewEmail(event.target.value)}
          />
          <button type="submit" className="rounded-full bg-brand px-4 py-2 text-sm font-semibold text-slate-900">
            Add email
          </button>
        </form>
      </section>

      <section className="rounded-3xl border border-red-200 bg-red-50 p-6 shadow-sm dark:border-red-400/50 dark:bg-red-500/10">
        <h2 className="text-lg font-semibold text-red-900 dark:text-red-200">Danger zone</h2>
        <p className="text-sm text-red-800 dark:text-red-200">Delete all decks, cards, and linked emails.</p>
        <button
          type="button"
          onClick={deleteAccount}
          className="mt-4 rounded-full border border-red-400 px-4 py-2 text-sm font-semibold text-red-700 dark:border-red-300 dark:text-red-100"
        >
          Delete account
        </button>
      </section>
    </div>
  );
}
