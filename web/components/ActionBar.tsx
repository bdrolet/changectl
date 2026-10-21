"use client";

import Link from "next/link";
import { useState, useTransition } from "react";

import {
  addComment,
  approveChange,
  requestChanges,
  submitChange,
} from "@/app/changes/actions";
import type { ActionResult } from "@/app/changes/actions";
import { Alert } from "@/components/Alert";
import { ConfirmSign } from "@/components/ConfirmSign";
import { ReleaseModal } from "@/components/ReleaseModal";
import type { ChangeDetail } from "@/lib/types";

export interface Viewer {
  id: string;
  name: string;
  email: string;
  isDocManager: boolean;
}

const PRIMARY =
  "rounded bg-zinc-900 px-3 py-1.5 text-sm text-white disabled:opacity-50";
const SECONDARY =
  "rounded border border-zinc-300 px-3 py-1.5 text-sm disabled:opacity-50";

export function ActionBar({
  change,
  viewer,
}: {
  change: ChangeDetail;
  viewer: Viewer;
}) {
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const [signing, setSigning] = useState(false);
  const [releasing, setReleasing] = useState(false);
  const [mode, setMode] = useState<"comment" | "changes" | null>(null);
  const [text, setText] = useState("");

  const isCreator = change.created_by === viewer.id;
  const mustSign = change.approvers.some(
    (a) => a.user_id === viewer.id && a.state !== "signed",
  );

  function run(call: () => Promise<ActionResult>, done?: () => void) {
    start(async () => {
      const res = await call();
      setError(res.ok ? null : res.error);
      if (res.ok) {
        setSigning(false);
        setMode(null);
        setText("");
        done?.();
      }
    });
  }

  const canComment =
    change.status === "approval" ||
    change.status === "implementation" ||
    change.status === "closed";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        {change.status === "initiate" && isCreator && (
          <>
            <Link href={`/changes/${change.id}/edit`} className={SECONDARY}>
              Edit
            </Link>
            <button
              type="button"
              disabled={pending}
              className={PRIMARY}
              onClick={() => run(() => submitChange(change.id))}
            >
              Submit
            </button>
          </>
        )}
        {change.status === "approval" && mustSign && (
          <>
            <button
              type="button"
              disabled={pending}
              className={PRIMARY}
              onClick={() => {
                setError(null);
                setSigning(true);
              }}
            >
              Approve
            </button>
            <button
              type="button"
              disabled={pending}
              className={SECONDARY}
              onClick={() => setMode(mode === "changes" ? null : "changes")}
            >
              Request changes
            </button>
          </>
        )}
        {change.status === "implementation" && viewer.isDocManager && (
          <button
            type="button"
            disabled={pending}
            className={PRIMARY}
            onClick={() => setReleasing(true)}
          >
            Release
          </button>
        )}
        {canComment && (
          <button
            type="button"
            disabled={pending}
            className={SECONDARY}
            onClick={() => setMode(mode === "comment" ? null : "comment")}
          >
            Comment
          </button>
        )}
      </div>

      {mode && (
        <form
          className="max-w-xl space-y-2"
          onSubmit={(e) => {
            e.preventDefault();
            run(() =>
              mode === "comment"
                ? addComment(change.id, text)
                : requestChanges(change.id, text),
            );
          }}
        >
          <label className="block text-sm font-medium">
            {mode === "comment" ? "Comment" : "What needs to change?"}
            <textarea
              required
              rows={3}
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="mt-1 w-full rounded border border-zinc-300 px-2 py-1 text-sm"
            />
          </label>
          <button type="submit" disabled={pending} className={PRIMARY}>
            {mode === "comment" ? "Post comment" : "Request changes"}
          </button>
        </form>
      )}

      <Alert message={signing ? null : error} />

      <ReleaseModal
        open={releasing}
        changeId={change.id}
        revisions={change.revisions}
        onClose={() => setReleasing(false)}
      />

      <ConfirmSign
        open={signing}
        name={viewer.name}
        email={viewer.email}
        number={change.number}
        title={change.title}
        pending={pending}
        error={signing ? error : null}
        onCancel={() => {
          if (!pending) setSigning(false);
        }}
        onConfirm={() => run(() => approveChange(change.id))}
      />
    </div>
  );
}
