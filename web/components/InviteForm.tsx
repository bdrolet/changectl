"use client";

import { useActionState, useRef } from "react";

import { inviteUser } from "@/app/users/actions";
import type { ActionResult } from "@/app/users/actions";
import { Alert } from "@/components/Alert";
import { ROLES } from "@/lib/roles";

const INPUT = "mt-1 rounded border border-zinc-300 px-2 py-1 text-sm";

export function InviteForm() {
  const formRef = useRef<HTMLFormElement>(null);
  const [state, action, pending] = useActionState<ActionResult | null, FormData>(
    async (_prev, form) => {
      const result = await inviteUser(form);
      if (result.ok) formRef.current?.reset();
      return result;
    },
    null,
  );

  return (
    <form ref={formRef} action={action} className="space-y-2">
      <div className="flex flex-wrap items-end gap-3">
        <label className="block text-sm font-medium">
          Email
          <input name="email" type="email" required className={`block ${INPUT}`} />
        </label>
        <label className="block text-sm font-medium">
          Name
          <input name="name" required className={`block ${INPUT}`} />
        </label>
        <label className="block text-sm font-medium">
          Role
          <select name="role" defaultValue={ROLES[0]} className={`block ${INPUT}`}>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 py-1.5 text-sm font-medium">
          <input name="is_doc_manager" type="checkbox" />
          Doc manager
        </label>
        <button
          type="submit"
          disabled={pending}
          className="rounded bg-zinc-900 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          Invite
        </button>
      </div>
      <Alert message={state && !state.ok ? state.error : null} />
    </form>
  );
}
