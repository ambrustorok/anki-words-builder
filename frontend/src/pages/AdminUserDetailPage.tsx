import { FormEvent, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "../lib/api";
import { LoadingScreen } from "../components/LoadingScreen";
import { useSession } from "../lib/session";

interface AdminUserDetailResponse {
  user: { id: string; native_language?: string; primary_email?: string; is_admin: boolean };
  emails: { id: string; email: string; is_primary: boolean }[];
  protectedEmails: string[];
}

export function AdminUserDetailPage() {
  const { userId } = useParams();
  const session = useSession();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [makePrimary, setMakePrimary] = useState(false);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["admin-user", userId],
    queryFn: () => apiFetch<AdminUserDetailResponse>(`/admin/users/${userId}`),
    enabled: session.data?.user.isAdmin && Boolean(userId)
  });

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
    await apiFetch(`/admin/users/${userId}/emails`, {
      method: "POST",
      json: { email, makePrimary }
    });
    setEmail("");
    setMakePrimary(false);
    refetch();
  };

  const deleteEmail = async (emailId: string) => {
    await apiFetch(`/admin/users/${userId}/emails/${emailId}`, { method: "DELETE" });
    refetch();
  };

  const setPrimaryEmail = async (emailId: string) => {
    await apiFetch(`/admin/users/${userId}/emails/${emailId}/primary`, { method: "POST" });
    refetch();
  };

  const renameEmail = async (emailId: string, current: string) => {
    const next = window.prompt("Update email", current);
    if (!next) return;
    await apiFetch(`/admin/users/${userId}/emails/${emailId}`, { method: "PATCH", json: { email: next } });
    refetch();
  };

  const toggleAdmin = async (makeAdmin: boolean) => {
    await apiFetch(`/admin/users/${userId}/admin`, { method: "POST", json: { makeAdmin } });
    refetch();
  };

  const deleteUser = async () => {
    const confirmed = window.confirm("Delete this user and all their data?");
    if (!confirmed) return;
    await apiFetch(`/admin/users/${userId}`, { method: "DELETE" });
    navigate("/admin/users");
  };

  const protectedEmailSet = new Set(data?.protectedEmails ?? []);
  const isProtected = data?.user.primary_email && protectedEmailSet.has(data.user.primary_email.toLowerCase());

  return (
    <section className="space-y-6">
      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <h1 className="text-xl font-semibold text-slate-900 dark:text-white">{data?.user.primary_email ?? "User"}</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">Native language: {data?.user.native_language ?? "—"}</p>
        <div className="mt-3 flex gap-2">
          <button
            className="rounded-full border border-slate-300 px-4 py-2 text-sm dark:border-slate-600 dark:text-slate-200"
            onClick={() => toggleAdmin(!data?.user.is_admin)}
          >
            {data?.user.is_admin ? "Revoke admin" : "Grant admin"}
          </button>
          {!isProtected && (
            <button className="rounded-full border border-red-300 px-4 py-2 text-sm text-red-600" onClick={deleteUser}>
              Delete user
            </button>
          )}
        </div>
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Emails</h2>
        <ul className="mt-4 divide-y divide-slate-100 text-sm dark:divide-slate-800">
          {data?.emails.map((item) => (
            <li key={item.id} className="flex items-center justify-between py-3">
              <div>
                <p className="font-medium text-slate-900 dark:text-white">{item.email}</p>
                {item.is_primary && <span className="text-xs text-slate-500 dark:text-slate-400">Primary</span>}
              </div>
              <div className="flex gap-2 text-xs">
                <button className="text-brand" onClick={() => renameEmail(item.id, item.email)}>
                  Rename
                </button>
                {!item.is_primary && (
                  <button className="text-brand" onClick={() => setPrimaryEmail(item.id)}>
                    Make primary
                  </button>
                )}
                {!item.is_primary && (
                  <button className="text-red-500" onClick={() => deleteEmail(item.id)}>
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
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
            <input type="checkbox" checked={makePrimary} onChange={(event) => setMakePrimary(event.target.checked)} />
            Make primary
          </label>
          <button type="submit" className="rounded-full bg-brand px-4 py-2 text-sm font-semibold text-slate-900">
            Add email
          </button>
        </form>
      </div>
    </section>
  );
}
