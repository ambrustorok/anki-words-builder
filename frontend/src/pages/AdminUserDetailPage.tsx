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

  const protectedEmailSet = new Set((data?.protectedEmails ?? []).map((entry) => entry.toLowerCase()));
  const isProtected = data?.user.primary_email && protectedEmailSet.has(data.user.primary_email.toLowerCase());

  return (
    <div className="space-y-8">
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
