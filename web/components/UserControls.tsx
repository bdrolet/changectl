"use client";

import { useState, useTransition } from "react";

import { updateUser } from "@/app/users/actions";
import type { ActionResult } from "@/app/users/actions";
import { Alert } from "@/components/Alert";
import { ROLES } from "@/lib/roles";
import type { UserOut } from "@/lib/types";

type Patch = Parameters<typeof updateUser>[2];

function useUpdate(user: UserOut) {
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  function apply(patch: Patch) {
    setError(null);
    start(async () => {
      const result: ActionResult = await updateUser(user.id, user.name, patch);
      if (!result.ok) setError(result.error);
    });
  }
  return { pending, error, apply };
}

export function RoleSelect({ user }: { user: UserOut }) {
  const { pending, error, apply } = useUpdate(user);
  return (
    <div>
      <select
        aria-label={`Role for ${user.name}`}
        value={user.role}
        disabled={pending}
        onChange={(e) => apply({ role: e.target.value })}
        className="rounded border border-zinc-300 px-2 py-1 text-sm"
      >
        {ROLES.map((r) => (
          <option key={r} value={r}>
            {r}
          </option>
        ))}
      </select>
      <Alert message={error} />
    </div>
  );
}

export function DocManagerToggle({ user }: { user: UserOut }) {
  const { pending, error, apply } = useUpdate(user);
  return (
    <div>
      <input
        type="checkbox"
        aria-label={`Doc manager: ${user.name}`}
        checked={user.is_doc_manager}
        disabled={pending}
        onChange={(e) => apply({ is_doc_manager: e.target.checked })}
      />
      <Alert message={error} />
    </div>
  );
}

export function DeactivateButton({ user }: { user: UserOut }) {
  const { pending, error, apply } = useUpdate(user);
  return (
    <div>
      <button
        type="button"
        disabled={pending}
        onClick={() => apply({ deactivated: !user.deactivated })}
        className="rounded border border-zinc-300 px-2 py-1 text-xs hover:bg-zinc-50 disabled:opacity-50"
      >
        {user.deactivated ? "Reactivate" : "Deactivate"}
      </button>
      <Alert message={error} />
    </div>
  );
}
