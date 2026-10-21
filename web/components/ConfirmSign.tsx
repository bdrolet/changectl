"use client";

import { useEffect, useRef } from "react";

export function ConfirmSign({
  open,
  name,
  email,
  number,
  title,
  pending,
  error,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  name: string;
  email: string;
  number: string;
  title: string;
  pending: boolean;
  error: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onCancel}
      onCancel={(e) => {
        if (pending) e.preventDefault();
      }}
      className="m-auto max-w-md rounded-lg p-6 shadow-xl backdrop:bg-black/40"
    >
      <h2 className="text-lg font-semibold">Sign approval</h2>
      <p className="mt-2 text-sm">
        You are signing as {name} ({email}). This records your approval of{" "}
        {number} &quot;{title}&quot; with the attached files as they are now.
      </p>
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {error}
        </p>
      )}
      <div className="mt-4 flex justify-end gap-3">
        <button
          type="button"
          disabled={pending}
          onClick={onCancel}
          className="rounded border disabled:opacity-50 border-zinc-300 px-3 py-1.5 text-sm"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={pending}
          onClick={onConfirm}
          className="rounded bg-zinc-900 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          Approve
        </button>
      </div>
    </dialog>
  );
}
