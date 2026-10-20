"use client";

import { useActionState, useRef } from "react";

import { createChange, updateChange } from "@/app/changes/actions";
import type { ActionResult } from "@/app/changes/actions";
import { Alert } from "@/components/Alert";

interface Initial {
  title: string;
  description: string;
  reason: string;
  justification: string;
}

const INPUT = "mt-1 w-full rounded border border-zinc-300 px-2 py-1 text-sm";

export function ChangeForm({
  changeId,
  initial,
}: {
  changeId?: string;
  initial?: Initial;
}) {
  const [state, action, pending] = useActionState<ActionResult | null, FormData>(
    async (_prev, form) =>
      changeId ? updateChange(changeId, form) : createChange(form),
    null,
  );
  const reasonRef = useRef<HTMLTextAreaElement>(null);
  const justificationRef = useRef<HTMLTextAreaElement>(null);

  return (
    <form action={action} className="max-w-2xl space-y-4">
      <label className="block text-sm font-medium">
        Title
        <input
          name="title"
          required
          defaultValue={initial?.title}
          className={INPUT}
        />
      </label>
      <label className="block text-sm font-medium">
        Description
        <textarea
          name="description"
          required
          rows={4}
          defaultValue={initial?.description}
          className={INPUT}
        />
      </label>
      <label className="block text-sm font-medium">
        Reason
        <textarea
          name="reason"
          ref={reasonRef}
          required
          rows={3}
          defaultValue={initial?.reason}
          className={INPUT}
        />
      </label>
      <div>
        <label className="block text-sm font-medium">
          Justification
          <textarea
            name="justification"
            ref={justificationRef}
            required
            rows={3}
            defaultValue={initial?.justification}
            className={INPUT}
          />
        </label>
        <button
          type="button"
          className="mt-1 text-xs text-blue-700 hover:underline"
          onClick={() => {
            if (reasonRef.current && justificationRef.current) {
              justificationRef.current.value = reasonRef.current.value;
            }
          }}
        >
          Same as reason
        </button>
      </div>
      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={pending}
          className="rounded bg-zinc-900 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {changeId ? "Save" : "Create change"}
        </button>
        {state?.ok && changeId && (
          <span role="status" className="text-sm text-green-700">
            Saved.
          </span>
        )}
      </div>
      <Alert message={state && !state.ok ? state.error : null} />
    </form>
  );
}
