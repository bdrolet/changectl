import { redirect } from "next/navigation";

import { auth } from "@/auth";
import { Alert } from "@/components/Alert";
import { InviteForm } from "@/components/InviteForm";
import {
  DeactivateButton,
  DocManagerToggle,
  RoleSelect,
} from "@/components/UserControls";
import { ApiError, apiFetch, redirectIfSignedOut } from "@/lib/api";
import type { UserOut } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function UsersPage() {
  const session = await auth();
  if (!session?.user) redirect("/signin");
  if (!session.user.isDocManager) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Users</h1>
        <p className="text-sm text-zinc-600">
          Only doc managers can manage users.
        </p>
      </div>
    );
  }

  let users: UserOut[] = [];
  let error: string | null = null;
  try {
    users = await apiFetch<UserOut[]>("/users");
  } catch (e) {
    redirectIfSignedOut(e);
    if (e instanceof ApiError && e.detail === "doc_manager_required") {
      return (
        <div className="space-y-4">
          <h1 className="text-2xl font-semibold">Users</h1>
          <p className="text-sm text-zinc-600">
            Only doc managers can manage users.
          </p>
        </div>
      );
    }
    error = e instanceof Error ? e.message : "Failed to load users";
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Users</h1>
      <InviteForm />
      <Alert message={error} />
      {users.length > 0 && (
        <table className="w-full text-left text-sm">
          <thead className="text-zinc-600">
            <tr>
              <th className="py-2 pr-4 font-medium">Name</th>
              <th className="py-2 pr-4 font-medium">Email</th>
              <th className="py-2 pr-4 font-medium">Role</th>
              <th className="py-2 pr-4 font-medium">Doc manager</th>
              <th className="py-2 pr-4 font-medium">Status</th>
              <th className="py-2 font-medium" />
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {users.map((u) => (
              <tr key={u.id} className="align-top">
                <td className="py-2 pr-4">{u.name}</td>
                <td className="py-2 pr-4">{u.email}</td>
                <td className="py-2 pr-4">
                  <RoleSelect user={u} />
                </td>
                <td className="py-2 pr-4">
                  <DocManagerToggle user={u} />
                </td>
                <td className="py-2 pr-4">
                  <span
                    className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                      u.deactivated
                        ? "bg-zinc-100 text-zinc-600"
                        : "bg-green-100 text-green-800"
                    }`}
                  >
                    {u.deactivated ? "deactivated" : "active"}
                  </span>
                </td>
                <td className="py-2">
                  <DeactivateButton user={u} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
