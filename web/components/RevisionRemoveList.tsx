"use client";

import { useState, useTransition } from "react";

import { removeRevision } from "@/app/changes/actions";
import { Alert } from "@/components/Alert";

export function RevisionRemoveList({
  changeId,
  revisions,
}: {
  changeId: string;
  revisions: { id: string; filename: string; documentTitle: string }[];
}) {
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  if (revisions.length === 0) {
    return <p className="text-sm text-zinc-600">No documents attached.</p>;
  }
  return (
    <div className="space-y-2">
      <ul className="divide-y divide-zinc-100 text-sm">
        {revisions.map((r) => (
          <li key={r.id} className="flex items-center gap-3 py-2">
            <span className="font-medium">{r.filename}</span>
            <span>{r.documentTitle}</span>
            <button
              type="button"
              disabled={pending}
              className="ml-auto text-red-700 hover:underline disabled:opacity-50"
              onClick={() =>
                start(async () => {
                  const res = await removeRevision(changeId, r.id);
                  setError(res.ok ? null : res.error);
                })
              }
            >
              Remove
            </button>
          </li>
        ))}
      </ul>
      <Alert message={error} />
    </div>
  );
}
