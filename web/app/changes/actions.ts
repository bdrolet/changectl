"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { describeError } from "@/lib/errors";

export type ActionResult = { ok: true } | { ok: false; error: string };

function field(form: FormData, name: string): string {
  const v = form.get(name);
  return typeof v === "string" ? v : "";
}

function fields(form: FormData) {
  return {
    title: field(form, "title"),
    description: field(form, "description"),
    reason: field(form, "reason"),
    justification: field(form, "justification"),
  };
}

function refresh(id: string) {
  revalidatePath("/changes");
  revalidatePath(`/changes/${id}`);
  revalidatePath("/documents");
}

async function run(id: string, call: () => Promise<unknown>): Promise<ActionResult> {
  try {
    await call();
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: describeError(e) };
    throw e;
  }
  refresh(id);
  return { ok: true };
}

function path(id: string, rest = ""): string {
  return `/changes/${encodeURIComponent(id)}${rest}`;
}

function post(body?: unknown): RequestInit {
  return {
    method: "POST",
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  };
}

export async function createChange(form: FormData): Promise<ActionResult> {
  let createdId: string;
  try {
    const created = await apiFetch<{ id: string }>("/changes", {
      method: "POST",
      body: JSON.stringify(fields(form)),
    });
    createdId = created.id;
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: describeError(e) };
    throw e;
  }
  revalidatePath("/changes");
  redirect(`/changes/${createdId}`);
}

export async function updateChange(
  id: string,
  form: FormData,
): Promise<ActionResult> {
  return run(id, () =>
    apiFetch(path(id), { method: "PATCH", body: JSON.stringify(fields(form)) }),
  );
}

export async function attachRevision(
  id: string,
  form: FormData,
): Promise<ActionResult> {
  const file = form.get("file");
  if (!(file instanceof File) || file.size === 0) {
    return { ok: false, error: "Choose a file to attach." };
  }
  const body = new FormData();
  body.set("file", file);
  const documentId = field(form, "document_id");
  const title = field(form, "title").trim();
  if (documentId) body.set("document_id", documentId);
  else if (title) body.set("title", title);
  else return { ok: false, error: "Pick a document or enter a title." };
  return run(id, () =>
    apiFetch(path(id, "/revisions"), { method: "POST", body }),
  );
}

export async function removeRevision(
  id: string,
  rid: string,
): Promise<ActionResult> {
  return run(id, () =>
    apiFetch(path(id, `/revisions/${encodeURIComponent(rid)}`), {
      method: "DELETE",
    }),
  );
}

export async function setApprovers(
  id: string,
  userIds: string[],
): Promise<ActionResult> {
  return run(id, () =>
    apiFetch(path(id, "/approvers"), {
      method: "PUT",
      body: JSON.stringify({ user_ids: userIds }),
    }),
  );
}

export async function submitChange(id: string): Promise<ActionResult> {
  return run(id, () => apiFetch(path(id, "/submit"), post()));
}

export async function approveChange(
  id: string,
  comment?: string,
): Promise<ActionResult> {
  return run(id, () =>
    apiFetch(path(id, "/approve"), post(comment ? { comment } : undefined)),
  );
}

export async function requestChanges(
  id: string,
  comment: string,
): Promise<ActionResult> {
  if (!comment.trim()) {
    return { ok: false, error: "Add a comment explaining what needs to change." };
  }
  return run(id, () => apiFetch(path(id, "/request-changes"), post({ comment })));
}

export async function addComment(
  id: string,
  body: string,
): Promise<ActionResult> {
  if (!body.trim()) return { ok: false, error: "Write a comment first." };
  return run(id, () => apiFetch(path(id, "/comments"), post({ body })));
}

export async function replaceReleaseFile(
  id: string,
  rid: string,
  form: FormData,
): Promise<ActionResult> {
  const file = form.get("file");
  if (!(file instanceof File) || file.size === 0) {
    return { ok: false, error: "Choose a file to attach." };
  }
  const body = new FormData();
  body.set("file", file);
  return run(id, () =>
    apiFetch(path(id, `/revisions/${encodeURIComponent(rid)}/release-file`), {
      method: "POST",
      body,
    }),
  );
}

export async function releaseChange(
  id: string,
  cutinDate: string,
): Promise<ActionResult> {
  return run(id, () => apiFetch(path(id, "/release"), post({ cutin_date: cutinDate })));
}
