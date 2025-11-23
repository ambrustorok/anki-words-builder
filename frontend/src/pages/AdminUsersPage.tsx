import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { apiFetch } from "../lib/api";
import { LoadingScreen } from "../components/LoadingScreen";
import { useSession } from "../lib/session";

interface AdminUsersResponse {
  users: { id: string; primary_email: string; native_language?: string; is_admin: boolean }[];
}

export function AdminUsersPage() {
  const session = useSession();
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => apiFetch<AdminUsersResponse>("/admin/users"),
    enabled: session.data?.user.isAdmin
  });

  if (!session.data?.user.isAdmin) {
    return <p className="text-sm text-slate-500">Admin access required.</p>;
  }

  if (isLoading) {
    return <LoadingScreen label="Loading users" />;
  }

  if (error) {
    return <p className="text-red-500">Failed to load users: {(error as Error).message}</p>;
  }

  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
      <h1 className="text-xl font-semibold text-slate-900 dark:text-white">Admin · Users</h1>
      <table className="mt-4 w-full text-sm">
        <thead className="text-left text-xs uppercase text-slate-500 dark:text-slate-300">
          <tr>
            <th className="px-3 py-2">Email</th>
            <th className="px-3 py-2">Native language</th>
            <th className="px-3 py-2">Admin</th>
            <th></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {data?.users?.map((user) => (
            <tr key={user.id}>
              <td className="px-3 py-2 text-brand">
                <Link to={`/admin/users/${user.id}`}>{user.primary_email ?? "—"}</Link>
              </td>
              <td className="px-3 py-2 text-slate-500 dark:text-slate-300">{user.native_language ?? "—"}</td>
              <td className="px-3 py-2 text-slate-500 dark:text-slate-300">{user.is_admin ? "Yes" : "No"}</td>
              <td className="px-3 py-2 text-right">
                <Link className="text-brand" to={`/admin/users/${user.id}`}>
                  Manage
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
