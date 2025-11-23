import { FormEvent, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "../lib/api";
import { useSession } from "../lib/session";
import { LoadingScreen } from "../components/LoadingScreen";

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
  const session = useSession();
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
    const fallbackLogout = `${window.location.origin}/cdn-cgi/access/logout`;
    window.location.href = response.logoutUrl ?? session.data?.logoutUrl ?? fallbackLogout;
  };

  return (
    <div className="space-y-6">
      {message && <p className="rounded-lg bg-emerald-50 px-4 py-2 text-sm text-emerald-700 dark:bg-emerald-400/20 dark:text-emerald-100">{message}</p>}
      {errMsg && <p className="rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700 dark:bg-red-500/20 dark:text-red-100">{errMsg}</p>}

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">OpenAI API key</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">Use your own key or fall back to the server default.</p>
          </div>
          {data?.apiKey?.has_key && (
            <span className="inline-flex items-center rounded-full border border-emerald-300/60 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 dark:border-emerald-400/40 dark:bg-emerald-400/10 dark:text-emerald-100">
              Key on file · {data.apiKey.masked ?? "••••"}
            </span>
          )}
        </div>
        <form className="mt-4 flex flex-col gap-3 md:flex-row" onSubmit={handleApiKey}>
          <input
            className="flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
            placeholder={data?.apiKey?.has_key ? "Update key" : "sk-..."}
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
          />
          <button type="submit" className="rounded-full bg-brand px-4 py-2 text-sm font-semibold text-slate-900">
            Save key
          </button>
          {data?.apiKey?.has_key && (
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
