"use client";

import { useActionState, useState } from "react";

import { attachRevision } from "@/app/changes/actions";
import type { ActionResult } from "@/app/changes/actions";
import { Alert } from "@/components/Alert";

const MAX_BYTES = 25 * 1024 * 1024;

export function FileDrop({
  changeId,
  documents,
}: {
  changeId: string;
  documents: { id: string; title: string }[];
}) {
  const [tooLarge, setTooLarge] = useState(false);
  const [documentId, setDocumentId] = useState("");
  const [state, action, pending] = useActionState<ActionResult | null, FormData>(
    async (_prev, form) => attachRevision(changeId, form),
    null,
  );

  return (
    <form
      action={action}
      className="max-w-2xl space-y-3"
      onSubmit={(e) => {
        if (tooLarge) e.preventDefault();
      }}
    >
      <label className="block text-sm font-medium">
        File
        <input
          type="file"
          name="file"
          required
          accept=".pdf,.docx,.xlsx"
          onChange={(e) => {
            const f = e.currentTarget.files?.[0];
            setTooLarge(f !== undefined && f.size > MAX_BYTES);
          }}
          className="mt-1 block w-full text-sm"
        />
      </label>
      <label className="block text-sm font-medium">
        Attach to existing document
        <select
          name="document_id"
          value={documentId}
          onChange={(e) => setDocumentId(e.target.value)}
          className="mt-1 w-full rounded border border-zinc-300 px-2 py-1 text-sm"
        >
          <option value="">New document</option>
          {documents.map((d) => (
            <option key={d.id} value={d.id}>
              {d.title}
            </option>
          ))}
        </select>
      </label>
      {documentId === "" && (
        <label className="block text-sm font-medium">
          New document title
          <input
            name="title"
            required
            className="mt-1 w-full rounded border border-zinc-300 px-2 py-1 text-sm"
          />
        </label>
      )}
      <button
        type="submit"
        disabled={pending || tooLarge}
        className="rounded bg-zinc-900 px-3 py-1.5 text-sm text-white disabled:opacity-50"
      >
        Attach file
      </button>
      <Alert
        message={
          tooLarge
            ? "Files must be 25 MB or smaller"
            : state && !state.ok
              ? state.error
              : null
        }
      />
    </form>
  );
}
