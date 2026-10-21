"use client";

import { useEffect, useRef, useState, useTransition } from "react";

import { releaseChange, replaceReleaseFile } from "@/app/changes/actions";
import type { RevisionOut } from "@/lib/types";

const MAX_BYTES = 25 * 1024 * 1024;

const EXTENSIONS: Record<string, string> = {
  "application/pdf": ".pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
    ".docx",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
};

function localToday(): string {
  const d = new Date();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

export function ReleaseModal({
  open,
  changeId,
  revisions,
  onClose,
}: {
  open: boolean;
  changeId: string;
  revisions: RevisionOut[];
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [cutin, setCutin] = useState(localToday);
  const [files, setFiles] = useState<Record<string, File | undefined>>({});
  const [tooLarge, setTooLarge] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  const single = revisions.length === 1 ? revisions[0] : null;
  const label = single
    ? `Release Rev ${single.next_revision_number ?? "?"}`
    : "Release";
  const blocked = Object.values(tooLarge).some(Boolean);

  function submit() {
    setError(null);
    start(async () => {
      for (const r of revisions) {
        const file = files[r.id];
        if (!file) continue;
        const form = new FormData();
        form.set("file", file);
        const res = await replaceReleaseFile(changeId, r.id, form);
        if (!res.ok) {
          setError(res.error);
          return;
        }
      }
      const res = await releaseChange(changeId, cutin);
      if (!res.ok) {
        setError(res.error);
        return;
      }
      onClose();
    });
  }

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onCancel={(e) => {
        if (pending) e.preventDefault();
      }}
      className="m-auto w-full max-w-lg rounded-lg p-6 shadow-xl backdrop:bg-black/40"
    >
      <h2 className="text-lg font-semibold">Release</h2>
      <ul className="mt-3 space-y-3 text-sm">
        {revisions.map((r) => (
          <li key={r.id} className="space-y-1">
            <div>
              <span className="font-medium">{r.document_title}</span>
              {!single && (
                <span className="ml-2 text-zinc-600">
                  Rev {r.next_revision_number ?? "?"}
                </span>
              )}
            </div>
            <div className="text-zinc-600">{r.original_filename}</div>
            <label className="block">
              Replace with clean file
              <input
                type="file"
                accept={EXTENSIONS[r.content_type]}
                disabled={pending}
                onChange={(e) => {
                  const f = e.currentTarget.files?.[0];
                  setFiles((m) => ({ ...m, [r.id]: f }));
                  setTooLarge((m) => ({
                    ...m,
                    [r.id]: f !== undefined && f.size > MAX_BYTES,
                  }));
                }}
                className="mt-1 block w-full text-sm"
              />
            </label>
            {tooLarge[r.id] && (
              <p role="alert" className="text-red-700">
                Files must be 25 MB or smaller
              </p>
            )}
          </li>
        ))}
      </ul>
      <label className="mt-4 block text-sm font-medium">
        Cut-in date
        <input
          type="date"
          required
          value={cutin}
          disabled={pending}
          onChange={(e) => setCutin(e.target.value)}
          className="mt-1 block rounded border border-zinc-300 px-2 py-1 text-sm"
        />
      </label>
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {error}
        </p>
      )}
      <div className="mt-4 flex justify-end gap-3">
        <button
          type="button"
          disabled={pending}
          onClick={onClose}
          className="rounded border border-zinc-300 px-3 py-1.5 text-sm disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={pending || blocked || !cutin}
          onClick={submit}
          className="rounded bg-zinc-900 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {label}
        </button>
      </div>
    </dialog>
  );
}
