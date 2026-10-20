"use client";

import { useState, useTransition } from "react";

import { setApprovers } from "@/app/changes/actions";
import { Alert } from "@/components/Alert";

export function ApproverPicker({
  changeId,
  users,
  selected,
}: {
  changeId: string;
  users: { id: string; name: string; role: string }[];
  selected: string[];
}) {
  const [chosen, setChosen] = useState<Set<string>>(new Set(selected));
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [pending, start] = useTransition();

  function toggle(id: string) {
    const next = new Set(chosen);
    if (!next.delete(id)) next.add(id);
    setChosen(next);
    setSaved(false);
  }

  return (
    <div className="max-w-2xl space-y-3">
      <ul className="space-y-1 text-sm">
        {users.map((u) => (
          <li key={u.id}>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={chosen.has(u.id)}
                onChange={() => toggle(u.id)}
              />
              <span>{u.name}</span>
              <span className="text-zinc-600">{u.role}</span>
            </label>
          </li>
        ))}
      </ul>
      <div className="flex items-center gap-3">
        <button
          type="button"
          disabled={pending}
          className="rounded bg-zinc-900 px-3 py-1.5 text-sm text-white disabled:opacity-50"
          onClick={() =>
            start(async () => {
              const res = await setApprovers(changeId, [...chosen]);
              setError(res.ok ? null : res.error);
              setSaved(res.ok);
            })
          }
        >
          Save approvers
        </button>
        {saved && (
          <span role="status" className="text-sm text-green-700">
            Saved.
          </span>
        )}
      </div>
      <Alert message={error} />
    </div>
  );
}
